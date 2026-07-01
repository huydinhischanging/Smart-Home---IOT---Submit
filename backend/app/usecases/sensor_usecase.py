# app/usecases/sensor_usecase.py

import logging
from app.extensions.database import db
from app.infrastructure.persistence.models.alert_rule_model import AlertRuleModel
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class SensorUseCase:

    _TEMP_HIGH_THRESHOLD = 30.0
    _HUMIDITY_HIGH_THRESHOLD = 75.0
    _LIGHT_LOW_THRESHOLD = 25.0
    _SUGGESTION_COOLDOWN_SECONDS = 10
    _user_suggestion_prefs = {}

    def __init__(
        self,
        device_repo,
        status_repo,
        sensor_repo,
        alert_repo,          # ⭐ Khớp với wiring.py
        realtime_notifier,   # ⭐ Khớp với wiring.py
        mqtt_publisher=None,
        ai_usecase=None
    ):
        self.device_repo = device_repo
        self.status_repo = status_repo
        self.sensor_repo = sensor_repo
        self.alert_repo = alert_repo
        self.realtime = realtime_notifier
        self.mqtt_publisher = mqtt_publisher
        self.ai_usecase = ai_usecase
        self._last_suggestions = {}

    @classmethod
    def set_user_suggestion_mute(cls, user_id, mute_minutes=60):
        if user_id is None:
            return None
        try:
            minutes = int(mute_minutes)
        except (TypeError, ValueError):
            minutes = 60
        now_utc = datetime.now(timezone.utc)
        until = now_utc if minutes <= 0 else now_utc.replace(microsecond=0) + timedelta(minutes=minutes)
        cls._user_suggestion_prefs[int(user_id)] = {
            "mute_until": until,
            "updated_at": now_utc,
        }
        return until

    @classmethod
    def get_user_suggestion_pref(cls, user_id):
        pref = cls._user_suggestion_prefs.get(int(user_id or 0), {})
        mute_until = pref.get("mute_until")
        updated_at = pref.get("updated_at")
        return {
            "mute_until": mute_until,
            "updated_at": updated_at,
            "is_muted": bool(mute_until and mute_until > datetime.now(timezone.utc)),
        }

    @classmethod
    def _is_suggestion_muted(cls, user_id, now_utc):
        if user_id is None:
            return False
        pref = cls._user_suggestion_prefs.get(int(user_id), {})
        mute_until = pref.get("mute_until")
        return bool(mute_until and mute_until > now_utc)

    # ==========================================================
    # 🔎 AI GET CONTEXT (Mới - Để Alfred đọc được sensor)
    # ==========================================================
    def get_latest_data(self):
        """Trả về dữ liệu cảm biến mới nhất cho AI"""
        try:
            # Lấy toàn bộ trạng thái hiện tại từ status_repository
            all_status = self.status_repo.get_all()
            context = {}
            for s in all_status:
                # Chỉ lấy các thiết bị có category là sensor hoặc có giá trị số
                try:
                    val = float(s.value)
                    context[s.device.code] = val
                except (ValueError, TypeError):
                    continue
            return context
        except Exception as e:
            logger.warning("Error getting sensor context: %s", e)
            return {}

    def get_latest_readings(self):
        """Alias for mqtt_listener: return dict with room_temp, humidity, light_level keys."""
        data = self.get_latest_data()
        return {
            "room_temp":   data.get("room_temp")   or data.get("temp"),
            "humidity":    data.get("humidity"),
            "light_level": data.get("light_level") or data.get("light"),
        }

    # ==========================================================
    # HANDLE SENSOR DATA (MQTT → Backend)
    # ==========================================================
    def handle_sensor_data(self, device_code, value):
        try:
            # PIR gửi string "DETECTED"/"CLEAR" — xử lý riêng, không cần numeric
            value_str = str(value).strip()
            try:
                numeric_value = float(value_str)
            except (ValueError, TypeError):
                numeric_value = None

            # Multi-tenant: update ALL devices with this code (one per tenant).
            # MQTT carries no user context, so we broadcast to every owner whose
            # physical device publishes under this code.
            devices = self.device_repo.get_all_by_code(device_code)
            if not devices:
                return False

            for device in devices:
                status = self.status_repo.get_or_create(device)
                status.value = value_str
                status.is_on = (value_str.upper() == "DETECTED") if numeric_value is None else True
                self.status_repo.save(status)

                # Record PIR motion for inactivity monitoring
                if device.device_type == 'pir' and status.is_on:
                    try:
                        from app.scheduler import record_pir_motion
                        record_pir_motion(device.user_id)
                    except Exception:
                        pass

                # Real-time map update via WebSocket
                try:
                    self.realtime.notify_device_status({
                        "event":       "DEVICE_UPDATED",
                        "device_id":   device.id,
                        "device_code": device.code,
                        "device_name": device.name,
                        "is_on":       status.is_on,
                        "value":       numeric_value if numeric_value is not None else value_str,
                    }, user_id=device.user_id)
                except Exception as _ws_err:
                    logger.debug("[SENSOR] WebSocket notify failed: %s", _ws_err)

                if numeric_value is not None:
                    self.sensor_repo.save(device.id, numeric_value)
                else:
                    pir_num = 1.0 if value_str.upper() == "DETECTED" else 0.0
                    self.sensor_repo.save(device.id, pir_num)

                self.check_sensor_alert(
                    device_id=device.id,
                    device_code=device.code,
                    current_value=numeric_value if numeric_value is not None else (1.0 if value_str.upper() == "DETECTED" else 0.0)
                )

                if numeric_value is not None:
                    self._handle_environmental_response(device, numeric_value)

            ai_usecase = self.ai_usecase or self._resolve_ai_usecase()
            if ai_usecase and numeric_value is not None:
                ai_usecase.process_sensors({"device": device_code, "value": numeric_value})

            db.session.commit()
            return True

        except Exception:
            logger.exception("[SENSOR] Error processing sensor data for '%s'", device_code)
            db.session.rollback()
            return False

    def _resolve_ai_usecase(self):
        """Lazy resolve AI usecase to avoid container circular dependency at startup."""
        try:
            from app.wiring import container
            self.ai_usecase = container.ai_usecase()
            return self.ai_usecase
        except Exception:
            return None

    def _infer_environment_metric(self, device):
        text = f"{getattr(device, 'code', '')} {getattr(device, 'name', '')}".lower()
        if any(k in text for k in ("temp", "nhiet", "temperature")):
            return "temperature"
        if any(k in text for k in ("humid", "doam", "humidity", "am")):
            return "humidity"
        if any(k in text for k in ("light", "lux", "den", "brightness", "anh sang")):
            return "light"
        return None

    def _cooldown_ok(self, key, now_utc):
        last_sent = self._last_suggestions.get(key)
        if not last_sent:
            return True
        return (now_utc - last_sent).total_seconds() >= self._SUGGESTION_COOLDOWN_SECONDS

    @staticmethod
    def _patient_present_in_room(user_id, room_id) -> bool:
        """Return True if a PIR sensor in room_id currently reports DETECTED.

        Returns True (allow suggestion) when:
          - room_id is None (no room context — can't gate)
          - no PIR device exists in the room (can't determine presence)
        Returns False (suppress confirmation popup) when:
          - at least one PIR in the room exists and ALL report CLEAR (is_on=False)
        """
        if not room_id:
            return True
        from app.infrastructure.persistence.models.device_model import Device
        from app.infrastructure.persistence.models.device_status_model import DeviceStatus
        pir_devices = (
            db.session.query(Device)
            .filter_by(user_id=user_id, room_id=room_id, is_deleted=False)
            .filter(Device.code.ilike("%pir%"))
            .all()
        )
        if not pir_devices:
            return True  # no PIR in room → can't tell, allow
        for pir in pir_devices:
            status = DeviceStatus.query.filter_by(device_id=pir.id).first()
            if status and status.is_on:
                return True  # at least one PIR DETECTED
        return False  # all PIR sensors CLEAR → patient not in this room

    @staticmethod
    def _prefer_same_room(candidates, trigger_room_id):
        """Return candidates sorted: same room first, then other rooms. Prefer OFF devices."""
        if not trigger_room_id:
            same, other = [], candidates
        else:
            same  = [d for d in candidates if getattr(d, "room_id", None) == trigger_room_id]
            other = [d for d in candidates if getattr(d, "room_id", None) != trigger_room_id]

        def _prefer_off(lst):
            off = [d for d in lst if not bool(getattr(getattr(d, "status", None), "is_on", False))]
            return off[0] if off else (lst[0] if lst else None)

        return _prefer_off(same) or _prefer_off(other)

    def _pick_cooling_device(self, user_id, trigger_room_id=None):
        devices = self.device_repo.get_all_active(user_id=user_id)
        _FAN_KW = {"fan", "quat", "quạt", "ac", "lanh", "aircon", "dieu hoa", "điều hòa"}
        candidates = []
        for d in devices:
            category = getattr(d, "category", "")
            if category in {"fan", "ac"}:
                candidates.append(d)
                continue
            text = f"{getattr(d,'code','').lower()} {getattr(d,'name','').lower()}"
            if any(k in text for k in _FAN_KW):
                candidates.append(d)
        if not candidates:
            return None
        return self._prefer_same_room(candidates, trigger_room_id)

    def _pick_lighting_device(self, user_id, trigger_room_id=None):
        devices = self.device_repo.get_all_active(user_id=user_id)
        candidates = []
        for d in devices:
            category = getattr(d, "category", "")
            text = f"{getattr(d, 'code', '')} {getattr(d, 'name', '')}".lower()
            if category in {"light", "switch"} or any(k in text for k in ("light", "den", "lamp")):
                candidates.append(d)
        if not candidates:
            return None
        return self._prefer_same_room(candidates, trigger_room_id)

    def _handle_environmental_response(self, trigger_device, current_value):
        user_id = getattr(trigger_device, "user_id", None)
        if user_id is None:
            return

        metric = self._infer_environment_metric(trigger_device)
        if metric == "temperature" and current_value <= self._TEMP_HIGH_THRESHOLD:
            return
        if metric == "humidity" and current_value <= self._HUMIDITY_HIGH_THRESHOLD:
            return
        if metric == "light" and current_value >= self._LIGHT_LOW_THRESHOLD:
            return
        if metric not in {"temperature", "humidity", "light"}:
            return

        now_utc = datetime.now(timezone.utc)
        if self._is_suggestion_muted(user_id, now_utc):
            return

        trigger_room_id = getattr(trigger_device, "room_id", None)
        action_device = (
            self._pick_lighting_device(user_id, trigger_room_id)
            if metric == "light"
            else self._pick_cooling_device(user_id, trigger_room_id)
        )

        if not action_device:
            cooldown_key_generic = (user_id, trigger_device.id, None, metric)
            if not self._cooldown_ok(cooldown_key_generic, now_utc):
                return
            self._last_suggestions[cooldown_key_generic] = now_utc
            alert_msg = (
                f"Suggestion: {'light level is low' if metric == 'light' else metric + ' is high'} ({current_value}). "
                f"Consider turning {'on light' if metric == 'light' else 'on fan/AC'}."
            )
            self.alert_repo.create(
                device_code=trigger_device.code,
                message=alert_msg,
                level="WARNING",
                user_id=user_id,
            )
            self.realtime.notify_alert(
                {
                    "device_code": trigger_device.code,
                    "message": alert_msg,
                    "level": "WARNING",
                    "timestamp": now_utc.isoformat(),
                },
                user_id=user_id,
            )
            return

        cooldown_key = (user_id, trigger_device.id, action_device.id, metric)
        if not self._cooldown_ok(cooldown_key, now_utc):
            return

        trigger_room_name = getattr(getattr(trigger_device, "room", None), "name", None)
        action_room_name  = getattr(getattr(action_device,  "room", None), "name", None)

        _SITUATION = {
            "temperature": "Nhiệt độ cao",
            "humidity":    "Độ ẩm cao",
            "light":       "Ánh sáng yếu",
        }
        situation_text = _SITUATION.get(metric, f"{metric} alert")
        room_ctx   = f" tại {trigger_room_name}" if trigger_room_name else ""
        action_loc = f" ({action_room_name})"    if action_room_name  else ""
        alert_msg = (
            f"Suggestion: {situation_text}{room_ctx} ({current_value}). "
            f"Bật {action_device.name}{action_loc} không?"
        )
        level = "WARNING"
        self._last_suggestions[cooldown_key] = now_utc

        self.alert_repo.create(
            device_code=trigger_device.code,
            message=alert_msg,
            level=level,
            user_id=user_id,
        )
        self.realtime.notify_alert(
            {
                "device_code": trigger_device.code,
                "message": alert_msg,
                "level": level,
                "timestamp": now_utc.isoformat(),
                "requires_confirmation": True,
                "suggested_action": {
                    "device_code": action_device.code,
                    "device_name": action_device.name,
                    "value": "ON",
                },
                "suggestion_kind": metric,
                "trigger_room":  trigger_room_name,
                "action_room":   action_room_name,
                "current_value": current_value,
            },
            user_id=user_id,
        )

    def check_sensor_alert(self, device_id, device_code, current_value):
        rule = AlertRuleModel.query.filter_by(device_id=device_id, is_active=True).first()
        if not rule: return None

        message = None
        level = "INFO"

        if rule.max_value is not None and current_value > rule.max_value:
            message = f"⚠ ALERT: {device_code} exceeded max ({current_value} > {rule.max_value})"
            level = "CRITICAL"
        elif rule.min_value is not None and current_value < rule.min_value:
            message = f"⚠ ALERT: {device_code} below min ({current_value} < {rule.min_value})"
            level = "WARNING"

        if message:
            self.alert_repo.create(device_code=device_code, message=message, level=level, user_id=rule.user_id)
            self.realtime.notify_alert({
                "device_code": device_code, "message": message, "level": level, "timestamp": datetime.now(timezone.utc).isoformat()
            }, user_id=rule.user_id)
        return message