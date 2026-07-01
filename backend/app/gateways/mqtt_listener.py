# app/gateways/mqtt_listener.py

import logging
import traceback  # ✅ In full stacktrace
from app.extensions.mqtt import mqtt
from app.wiring import container
from app.presentation.api.coospo_api import on_heart_rate_received
from app.usecases.patient_hr_persistence import persist_patient_hr_record

logger = logging.getLogger(__name__)

try:
    from app.ai.services.heart_rate_ai import get_monitor
except ImportError:
    get_monitor = None


def _extract_device_route(topic: str, prefix: str):
    if not topic.startswith(prefix):
        return None, None

    parts = [part.strip() for part in topic.split("/")]
    if len(parts) == 3:
        return parts[2], None
    if len(parts) == 4:
        return parts[3], parts[2]
    return None, None


def init_mqtt_listener(app):
    verbose_sensor_log = bool(app.config.get("MQTT_VERBOSE_SENSOR_LOG", False))
    debug_log_enabled = bool(app.config.get("MQTT_DEBUG_LOG", False))

    if debug_log_enabled:
        logger.setLevel(logging.DEBUG)
        logger.info("[MQTT] Debug log enabled for mqtt_listener")

    # ==========================================
    # 1️⃣ WHEN CONNECTED TO BROKER
    # ==========================================
    @mqtt.on_connect()
    def handle_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info("[MQTT] Connected to EMQX Broker")

            mqtt.subscribe("home/status/#")
            mqtt.subscribe("home/sensors/#")

            logger.info("[MQTT] Subscribed to home/status/# and home/sensors/#")
        else:
            logger.error("[MQTT] Connection failed with code %s", rc)

    # ==========================================
    # 2️⃣ WHEN MESSAGE RECEIVED
    # ==========================================
    @mqtt.on_message()
    def handle_mqtt_message(client, userdata, message):

        # 🔥 VERY IMPORTANT:
        # MQTT chạy ở thread riêng → cần Flask app context
        with app.app_context():

            try:
                # -------------------------------
                # Clean topic
                # -------------------------------
                topic = message.topic.strip()

                # -------------------------------
                # Clean payload format
                # -------------------------------
                payload_raw = message.payload.decode(errors="ignore").strip()

                # Nếu sender gửi "Payload: 42" → convert thành "42"
                if payload_raw.lower().startswith("payload:"):
                    payload = payload_raw.split(":", 1)[1].strip()
                else:
                    payload = payload_raw

                logger.debug("[MQTT RECEIVE] %r -> %r", topic, payload)

                # ======================================================
                # SENSOR DATA
                # ======================================================
                if topic.startswith("home/sensors/"):
                    device_code, device_type = _extract_device_route(topic, "home/sensors/")
                    if not device_code:
                        logger.warning("[MQTT] Invalid sensor topic: %s", topic)
                        return

                    if device_type:
                        logger.debug("[MQTT SENSOR V2] type=%s code=%s", device_type, device_code)

                    # Keep light telemetry visible at INFO for quick field diagnostics.
                    if device_code == "light" or verbose_sensor_log:
                        logger.info("[MQTT SENSOR] %s=%s", device_code, payload)

                    # ✅ Special handler for Coospo H6 heart rate
                    if device_code == "heart_rate":
                        try:
                            bpm = int(payload)
                            on_heart_rate_received(bpm)
                            logger.debug("[COOSPO] Heart Rate API updated: %d BPM", bpm)

                            if 50 <= bpm < 100:
                                saved = persist_patient_hr_record(
                                    bpm,
                                    severity="normal",
                                    source="coospo_backend",
                                    throttle_sec=10,
                                )
                                if saved:
                                    logger.debug("[PATIENT HR] Saved normal BPM=%d for %s user(s)", bpm, saved)

                            # ✅ Emit WebSocket real-time — scoped per user to prevent cross-user health data leakage
                            try:
                                from app.infrastructure.persistence.models.user_model import UserModel
                                notifier = container.realtime_notifier()
                                hr_payload = {
                                    "code":        "heart_rate",
                                    "value":       float(bpm),
                                    "heart_rate":  bpm,
                                    "name":        "Coospo H6",
                                    "device_name": "coospo_h6",
                                    "event":       "HEART_RATE_UPDATE",
                                }
                                active_user_ids = [
                                    uid for (uid,) in
                                    UserModel.query.filter_by(is_active=True)
                                    .with_entities(UserModel.id).all()
                                ]
                                for uid in active_user_ids:
                                    notifier.notify_device_status(hr_payload, user_id=uid)
                            except Exception as ws_err:
                                logger.warning("[COOSPO] WebSocket emit error: %s", ws_err)

                            # ✅ Heart Rate AI — pass real sensor context from DB
                            if get_monitor:
                                try:
                                    monitor = get_monitor()
                                    if monitor is not None and hasattr(monitor, 'on_bpm_update'):
                                        # Fetch latest sensor readings from DB for accurate inference
                                        room_temp   = None
                                        humidity    = None
                                        light_level = None
                                        try:
                                            sensor_uc = container.sensor_usecase()
                                            latest = sensor_uc.get_latest_readings() if hasattr(sensor_uc, 'get_latest_readings') else {}
                                            room_temp   = latest.get("room_temp")
                                            humidity    = latest.get("humidity")
                                            light_level = latest.get("light_level")
                                        except Exception as ctx_err:
                                            logger.warning("[HeartRateAI] Could not fetch sensor context: %s", ctx_err)

                                        monitor.on_bpm_update(
                                            bpm,
                                            room_temp=room_temp,
                                            humidity=humidity,
                                            light_level=light_level,
                                        )
                                except Exception as ai_err:
                                    logger.warning("[HeartRateAI] Error: %s", ai_err)
                        except ValueError:
                            logger.warning("[COOSPO] Invalid BPM format: %s", payload)
                        return

                    # NOTE: special handling for batched coospo data payload (JSON)
                    if device_code == "data":
                        try:
                            import json
                            data = json.loads(payload)
                            bpm = data.get("heart_rate") or data.get("hr")
                            room_temp = data.get("room_temp") or data.get("temperature")
                            humidity = data.get("humidity")
                            light_level = data.get("light_level")
                            if bpm is not None:
                                bpm_int = int(bpm)
                                on_heart_rate_received(
                                    bpm_int,
                                    room_temp=float(room_temp) if room_temp is not None else None,
                                    humidity=float(humidity) if humidity is not None else None,
                                    light_level=float(light_level) if light_level is not None else None,
                                )
                                logger.debug("[COOSPO] Heart Rate API updated from data: %d BPM", bpm_int)
                                return
                        except Exception:
                            pass

                    try:
                        success = container.sensor_usecase().handle_sensor_data(
                            device_code,
                            payload
                        )

                        if success:
                            logger.debug("[AI PROCESSED] Sensor OK: %s", device_code)
                        else:
                            logger.warning("[SYSTEM] Unknown sensor: %s", device_code)

                    except Exception:
                        logger.exception("[CRITICAL] Sensor processing failed")

                # ======================================================
                # DEVICE STATUS UPDATE
                # ======================================================
                elif topic.startswith("home/status/"):
                    device_code, device_type = _extract_device_route(topic, "home/status/")
                    if not device_code:
                        logger.warning("[MQTT] Invalid status topic: %s", topic)
                        return

                    if device_type:
                        logger.debug("[MQTT STATUS V2] type=%s code=%s", device_type, device_code)

                    try:
                        container.device_usecase().update_device_status(
                            device_code=device_code,
                            value=payload,
                            source="MQTT",
                        )

                        logger.debug("[DEVICE UPDATED] %s", device_code)

                    except Exception:
                        logger.exception("[CRITICAL] Device status update failed")

                # ======================================================
                # UNKNOWN TOPIC
                # ======================================================
                else:
                    logger.warning("[MQTT] Unhandled topic: %s", topic)

            except Exception:
                # Nếu crash ở mức outer handler
                logger.exception("[FATAL MQTT ERROR] Unexpected failure")