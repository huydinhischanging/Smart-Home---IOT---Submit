# app/ai/services/heart_rate_ai.py
import time
import logging
import threading
import pandas as pd

from app.ai.inference.model_loader import ModelLoader
from app.ai.inference.anomaly_detector import AnomalyDetector
from app.ai.inference.mood_predictor import MoodPredictor
from app.ai.services.hrv_analyzer import HRVAnalyzer
from app.usecases.patient_hr_persistence import persist_patient_hr_record

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "heart_rate", "room_temp", "humidity",
    "light_level", "hour", "is_night", "is_dark"
]

_DEFAULTS = {"room_temp": 24.0, "humidity": 50.0, "light_level": 100.0}

ALERT_COOLDOWN_SEC = 30


class HeartRateMonitor:

    def __init__(self, realtime_notifier=None):
        self.loader           = ModelLoader()
        self.anomaly_detector = AnomalyDetector(self.loader)
        self.mood_predictor   = MoodPredictor(self.loader)
        self.hrv_analyzer     = HRVAnalyzer()
        self._last_alert_time = 0.0
        self.realtime         = realtime_notifier

    def on_bpm_update(self, bpm: int,
                      room_temp: float = None,
                      humidity: float = None,
                      light_level: float = None):
        try:
            bpm = int(bpm)
        except (ValueError, TypeError):
            logger.warning("[HeartRateAI] Invalid BPM value: %s", bpm)
            return

        # Use defaults when side-sensor context is unavailable.
        room_temp   = room_temp   if room_temp   is not None else _DEFAULTS["room_temp"]
        humidity    = humidity    if humidity    is not None else _DEFAULTS["humidity"]
        light_level = light_level if light_level is not None else _DEFAULTS["light_level"]

        using_defaults = (
            room_temp   == _DEFAULTS["room_temp"] and
            humidity    == _DEFAULTS["humidity"] and
            light_level == _DEFAULTS["light_level"]
        )
        if using_defaults:
            logger.debug("[HeartRateAI] Using default sensor values")

        # HRV — update sliding window on every reading (before tier checks)
        self.hrv_analyzer.add_bpm(bpm)
        hrv_result = self.hrv_analyzer.compute()   # None if < 5 samples yet
        if hrv_result:
            logger.info(
                "[HRV] RMSSD=%.1f ms SDNN=%.1f ms pNN50=%.1f%% → %s",
                hrv_result.rmssd, hrv_result.sdnn, hrv_result.pnn50,
                hrv_result.risk_level,
            )

        # Tier 1: rule-based thresholds
        risk = "normal"
        if bpm >= 130:
            risk = "emergency"
            logger.error("[HeartRateAI] EMERGENCY: BPM=%d", bpm)
        elif bpm >= 100:
            risk = "warning_high"
            logger.warning("[HeartRateAI] WARNING HIGH: BPM=%d", bpm)
        elif bpm < 50:
            risk = "warning_low"
            logger.warning("[HeartRateAI] WARNING LOW: BPM=%d", bpm)
        else:
            logger.debug("[HeartRateAI] Normal BPM=%d", bpm)

        # Tier 2 & 3: ML inference
        scaler = self.loader.get_model("scaler")
        if scaler is None:
            logger.warning("[HeartRateAI] Scaler not loaded -- skipping ML inference")
            self._emit_alert(bpm, risk, False, "unknown", hrv_result)
            return

        now      = time.localtime()
        hour     = now.tm_hour
        is_night = 1 if hour < 6 or hour >= 22 else 0
        is_dark  = 1 if hour < 8 or hour >= 18 else 0

        # Keep feature order aligned with training pipeline.
        x_arr = pd.DataFrame([[
            float(bpm), float(room_temp), float(humidity),
            float(light_level), float(hour),
            float(is_night), float(is_dark),
        ]], columns=FEATURE_NAMES)

        try:
            x_scaled   = scaler.transform(x_arr)
            is_anomaly = bool(self.anomaly_detector.detect(x_scaled))
            mood       = str(self.mood_predictor.predict(x_scaled))

            logger.info("[HeartRateAI] Anomaly=%s, Mood=%s, Context=(temp=%s, hum=%s, light=%s)",
                        is_anomaly, mood, room_temp, humidity, light_level)

            if is_anomaly and risk == "normal":
                risk = "anomaly"
            # HRV-based escalation: very_low_hrv with normal BPM is still a concern
            if hrv_result and hrv_result.risk_level == "very_low_hrv" and risk == "normal":
                risk = "anomaly"

            self._emit_alert(bpm, risk, is_anomaly, mood, hrv_result)

        except Exception as e:
            logger.error("[HeartRateAI] ML inference error: %s", e, exc_info=True)
            self._emit_alert(bpm, risk, False, "unknown", hrv_result)

    def _emit_alert(self, bpm: int, risk: str,
                    is_anomaly: bool, mood: str, hrv_result=None):
        # Skip downstream work for healthy readings.
        if risk == "normal" and not is_anomaly:
            return

        now = time.time()
        # Cooldown prevents repeated alerts during noisy bursts.
        if now - self._last_alert_time < ALERT_COOLDOWN_SEC:
            return
        self._last_alert_time = now

        try:
            from app.extensions.socketio import socketio
            severity = {
                "emergency":    "critical",
                "warning_high": "warning",
                "warning_low":  "caution",
                "anomaly":      "caution",
            }.get(risk, "normal")

            payload = {
                "bpm":        int(bpm),
                "risk":       str(risk),
                "severity":   str(severity),
                "is_anomaly": bool(is_anomaly),
                "mood":       str(mood),
                "timestamp":  time.strftime("%H:%M:%S"),
                "hrv":        hrv_result.to_dict() if hrv_result else None,
            }

            socketio.emit("hr_alert", payload)
            # Compatibility fallback: many UI paths already listen on "alert".
            socketio.emit("alert", {
                "device_code": "heart_rate",
                "level": str(severity).upper(),
                "message": f"Heart Rate {int(bpm)} BPM ({str(risk).replace('_', ' ')})",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            
            # ✨ Emit mood to frontend for theme change
            if self.realtime:
                try:
                    mood_payload = {
                        "mood": str(mood),
                        "bpm": int(bpm),
                        "risk": str(risk),
                        "timestamp": time.strftime("%H:%M:%S")
                    }
                    # Get all active users for broadcasting
                    from app.infrastructure.persistence.models.user_model import UserModel
                    users = UserModel.query.filter(UserModel.is_active.is_(True)).all()
                    for user in users:
                        self.realtime.notify_ai_mood(mood_payload, user_id=user.id)
                except Exception as mood_err:
                    logger.warning("[HeartRateAI] Failed to emit mood: %s", mood_err)
            
            logger.info("[HeartRateAI] Emitted hr_alert -- severity=%s", severity)

            # Store HR alert history for REST API endpoint
            try:
                from app.presentation.api.coospo_api import add_hr_alert
                add_hr_alert(payload)
            except Exception as err:
                logger.warning("[HeartRateAI] Failed to persist hr_alert: %s", err)

            # Also persist into the main alerts table used by /api/alerts.
            try:
                from app.extensions.database import db
                from app.infrastructure.persistence.models.user_model import UserModel
                from app.wiring import container

                level_for_alerts = {
                    "critical": "critical",
                    "warning": "warning",
                    "caution": "warning",
                }.get(str(severity).lower(), "info")
                alert_message = f"Heart Rate {int(bpm)} BPM ({str(risk).replace('_', ' ')})"

                users = (
                    UserModel.query
                    .filter(UserModel.is_active.is_(True))
                    .filter(UserModel.role.in_(["user", "admin"]))
                    .all()
                )

                alert_usecase = container.alert_usecase()
                created = 0
                for user in users:
                    alert_usecase.create_alert(
                        device_code="heart_rate",
                        message=alert_message,
                        level=level_for_alerts,
                        user_id=user.id,
                    )
                    created += 1

                if created:
                    db.session.commit()
                    logger.info("[HeartRateAI] Saved %d alert row(s) for AlertsCenter", created)
                else:
                    logger.warning("[HeartRateAI] No active users found to persist alerts")
            except Exception as err:
                try:
                    from app.extensions.database import db
                    db.session.rollback()
                except Exception:
                    pass
                logger.warning("[HeartRateAI] Failed to persist alerts table rows: %s", err)

            try:
                hrv_kwargs = {}
                if hrv_result:
                    hrv_kwargs = {
                        "hrv_rmssd":   hrv_result.rmssd,
                        "hrv_sdnn":    hrv_result.sdnn,
                        "hrv_pnn50":   hrv_result.pnn50,
                        "hrv_mean_rr": hrv_result.mean_rr,
                        "hrv_risk":    hrv_result.risk_level,
                    }
                saved = persist_patient_hr_record(
                    bpm,
                    severity=severity,
                    risk=str(risk),
                    mood=str(mood),
                    source="coospo_ai",
                    force=True,
                    **hrv_kwargs,
                )
                if saved:
                    logger.info("[HeartRateAI] Saved alert BPM=%d for %d user(s)", int(bpm), saved)
            except Exception as err:
                logger.warning("[HeartRateAI] Failed to persist patient HR record: %s", err)

        except Exception as e:
            logger.error("[HeartRateAI] Socket emit error: %s", e, exc_info=True)


# Thread-safe singleton
_monitor_instance = None
_monitor_lock     = threading.Lock()


def get_monitor():
    global _monitor_instance
    if _monitor_instance is None:
        with _monitor_lock:
            if _monitor_instance is None:
                try:
                    from app.wiring import container
                    realtime_notifier = container.realtime_notifier()
                    _monitor_instance = HeartRateMonitor(realtime_notifier=realtime_notifier)
                    logger.info("[HeartRateAI] Monitor started")
                except Exception as exc:
                    logger.error("[HeartRateAI] Failed to create monitor: %s", exc, exc_info=True)
    return _monitor_instance


