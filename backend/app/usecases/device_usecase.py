# app/usecases/device_usecase.py
import logging
from typing import Dict, List, Optional, Any
from app.extensions.database import db

logger = logging.getLogger(__name__)


class DeviceUseCase:
    ALLOWED_CATEGORIES = {
        "sensor", "actuator", "light", "fan", "ac", "camera", "lock", "switch", "tv", "speaker", "other"
    }

    def __init__(self, device_repo, status_repo, log_repo, mqtt_publisher, realtime_notifier):
        self.device_repo = device_repo
        self.status_repo = status_repo
        self.log_repo = log_repo
        self.mqtt = mqtt_publisher
        self.realtime = realtime_notifier

    @staticmethod
    def _to_optional_int(value):
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _infer_category(cls, raw_category: Any, raw_type: str) -> str:
        category = str(raw_category or "").strip().lower()
        if category in cls.ALLOWED_CATEGORIES:
            return category

        device_type = str(raw_type or "").strip().lower()
        if device_type in {"temperature", "humidity", "motion", "light_sensor", "sensor"}:
            return "sensor"
        if device_type in {"relay", "switch", "dimmer", "actuator"}:
            return "actuator"
        if device_type in cls.ALLOWED_CATEGORIES:
            return device_type
        return "sensor"

    @classmethod
    def _normalize_create_payload(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        # Accept both legacy keys and scalable naming aliases.
        name = str(data.get("name") or data.get("device_name") or "").strip()
        code = str(data.get("code") or data.get("device_code") or data.get("device_id") or "").strip()
        raw_type = str(data.get("device_type") or data.get("type") or "switch").strip()

        control_types = data.get("control_types")
        if isinstance(control_types, list):
            normalized_control_types = [str(v).strip() for v in control_types if str(v).strip()]
        elif raw_type:
            normalized_control_types = [raw_type]
        else:
            normalized_control_types = ["switch"]

        return {
            "name": name,
            "code": code,
            "icon": data.get("icon") or "💡",
            "category": cls._infer_category(data.get("category"), raw_type),
            "control_types": normalized_control_types,
            "map_x": data.get("map_x"),
            "map_y": data.get("map_y"),
            "room_id": cls._to_optional_int(data.get("room_id") if "room_id" in data else data.get("location")),
            # Metadata is accepted for forward compatibility and can be persisted later
            # without breaking API contracts.
            "metadata": data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
            "device_type": raw_type,
        }

    @staticmethod
    def _device_type_for(device) -> str:
        return getattr(device, "device_type", None) or (device.types_list[0] if device.types_list else "switch")

    @classmethod
    def _group_matches(cls, device, category_group: Optional[str]) -> bool:
        if not category_group:
            return True
        group = str(category_group).strip().lower()
        category = str(getattr(device, "category", "") or "").strip().lower()
        if group in {"sensor", "sensors"}:
            return category == "sensor"
        if group in {"actuator", "actuators"}:
            return category != "sensor"
        return category == group

    @classmethod
    def _device_matches_descriptor(cls, device, category_group: Optional[str], device_type: Optional[str]) -> bool:
        if not device or getattr(device, "is_deleted", False):
            return False
        if not cls._group_matches(device, category_group):
            return False
        if not device_type:
            return True
        return cls._device_type_for(device).strip().lower() == str(device_type).strip().lower()

    @classmethod
    def _serialize_device(cls, device) -> Dict[str, Any]:
        status = device.status
        raw_value = status.value if status else "OFF"
        room_name = device.room.name if (hasattr(device, 'room') and device.room) else "General Area"
        device_type = cls._device_type_for(device)
        try:
            parsed_value = float(raw_value)
        except Exception:
            parsed_value = raw_value
        return {
            "id": device.id,
            "name": device.name,
            "code": device.code,
            "icon": device.icon,
            "room": room_name,
            "type": device_type,
            "device_type": device_type,
            "control_types": list(device.types_list or []),
            "category": device.category,
            "metadata": getattr(device, "metadata_dict", {}),
            "room_id": device.room_id,
            "map_x": device.map_x,
            "map_y": device.map_y,
            "is_on": status.is_on if status else False,
            "value": parsed_value,
            "management": {
                "device_name": device.name,
                "device_code": device.code,
                "device_type": device_type,
                "category": device.category,
                "location": room_name,
                "room_id": device.room_id,
                "metadata": getattr(device, "metadata_dict", {}),
            },
        }

    def get_device(self, device_code: str, user_id: Optional[int] = None):
        return self.device_repo.get_by_code(device_code, user_id=user_id)

    def get_device_snapshot(
        self,
        device_code: str,
        user_id: Optional[int] = None,
        category_group: Optional[str] = None,
        device_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        device = self.get_device(device_code, user_id=user_id)
        if not self._device_matches_descriptor(device, category_group, device_type):
            return None
        return self._serialize_device(device)

    def get_all_devices(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        devices = self.device_repo.get_all_active(user_id=user_id)
        return [self._serialize_device(d) for d in devices]

    def create_device(self, data: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
        try:
            normalized = self._normalize_create_payload(data)
            name = normalized["name"]
            if not name:
                return {"success": False, "message": "Ten thiet bi khong duoc de trong", "status": 400}

            # ✅ Auto-suffix neu ten trung: "den" -> "den 2" -> "den 3"
            original_name = name
            counter = 2
            while self.device_repo.exists_by_name(name, user_id=user_id):
                name = f"{original_name} {counter}"
                counter += 1

            # ✅ Auto-suffix code neu trung
            base_code = (normalized["code"] or original_name.lower().replace(" ", "_")).strip()
            code = base_code
            code_counter = 2
            while self.device_repo.exists_by_code(code, user_id=user_id):
                code = f"{base_code}_{code_counter}"
                code_counter += 1

            device = self.device_repo.create(
                name=name,
                code=code,
                icon=normalized["icon"],
                control_types=normalized["control_types"],
                category=normalized["category"],
                device_type=normalized["device_type"],
                metadata_json=normalized["metadata"],
                map_x=normalized["map_x"],
                map_y=normalized["map_y"],
                room_id=normalized["room_id"],
                user_id=user_id,
            )
            db.session.commit()
            logger.info("[DEVICE CREATED] user_id=%s device_id=%d code=%s name=%s",
                        user_id, device.id, code, name)
            return {
                "success": True,
                "device_id": device.id,
                "name": name,
                "code": code,
                "category": normalized["category"],
                "type": normalized["device_type"],
                "device_type": normalized["device_type"],
                "room_id": normalized["room_id"],
                "metadata": normalized["metadata"],
            }
        except Exception as e:
            db.session.rollback()
            logger.error("[DEVICE CREATE FAILED] user_id=%s name=%s | error: %s",
                         user_id, name, e, exc_info=True)
            return {"success": False, "message": str(e), "status": 500}

    def delete_device(self, code: str, user_id=None):
        try:
            device = self.device_repo.get_by_code(code, user_id=user_id)
            if not device or device.is_deleted:
                return {"success": False, "status": 404}
            device_id   = device.id
            device_name = device.name
            device_code = device.code
            self.log_repo.add(device_code=device_code, device_id=device_id, action="DELETE", source="API", user_id=user_id)
            if device.status is not None:
                self.status_repo.delete(device.status)
            self.device_repo.delete(device)
            db.session.commit()
            self.realtime.notify_device_status({
                "event": "DEVICE_DELETED",
                "device_id": device_id,
                "device_name": device_name
            }, user_id=user_id)
            return {"success": True}
        except Exception as e:
            db.session.rollback()
            logger.error("delete_device error: %s", e, exc_info=True)
            return {"success": False, "status": 500}

    def update_device_status(self, device_code: str, value: str, source: str = "MQTT", user_id=None):
        """Called by mqtt_listener when Arduino publishes home/status/{code}.
        
        Args:
            device_code: Device identifier from MQTT topic
            value: New device status value
            source: Source of update (MQTT, API, SYSTEM)
            user_id: Optional user scope. When provided, updates only that
                     user's device. When absent (MQTT), updates ALL tenants
                     who have a device with this code (multi-tenant broadcast).
        """
        try:
            if user_id is not None:
                devices = [self.device_repo.get_by_code(device_code, user_id=user_id)]
                devices = [d for d in devices if d and not d.is_deleted]
            else:
                # MQTT has no user context — broadcast to every tenant's device
                devices = self.device_repo.get_all_by_code(device_code)

            if not devices:
                logger.warning(
                    "[MULTI-TENANT] update_device_status: unknown device code=%r for user_id=%s",
                    device_code, user_id
                )
                return

            value_upper = value.strip().upper()
            for device in devices:
                status = self.status_repo.get_or_create(device)
                status.is_on = value_upper == "ON"
                status.value = value.strip()
                self.status_repo.save(status)
                self.log_repo.add(
                    device_code=device_code,
                    device_id=device.id,
                    action=f"STATUS: {value}",
                    source=source,
                )
                self.realtime.notify_device_status({
                    "event":       "DEVICE_UPDATED",
                    "device_id":   device.id,
                    "device_code": device.code,
                    "device_name": device.name,
                    "is_on":       status.is_on,
                    "value":       None,
                }, user_id=device.user_id)

            db.session.commit()
            logger.debug("update_device_status: [%s] -> %s (%d device(s))", device_code, value, len(devices))
        except Exception as e:
            db.session.rollback()
            logger.error("update_device_status error: %s", e, exc_info=True)

    def update_device_coords(self, data: dict, user_id=None):
        try:
            device = (
                self.device_repo.get_by_id(data.get("id"), user_id=user_id)
                or self.device_repo.get_by_name(data.get("name"), user_id=user_id)
            )
            if not device or device.is_deleted:
                return {"success": False, "status": 404}
            if user_id is not None and device.user_id != user_id:
                return {"success": False, "status": 403}
            # ✅ Handle null coords (remove from map)
            mx = data.get("map_x")
            my = data.get("map_y")
            device.map_x = float(mx) if mx is not None else None
            device.map_y = float(my) if my is not None else None
            if "room_id" in data:
                device.room_id = int(data["room_id"]) if data["room_id"] is not None else None
            db.session.commit()
            return {"success": True}
        except Exception as e:
            logger.error("update_device_coords error: %s", e, exc_info=True)
            db.session.rollback()
            return {"success": False, "status": 500}

    def control_device(self, data: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
        device = (
            self.device_repo.get_by_id(data.get("device_id"), user_id=user_id)
            or self.device_repo.get_by_code(data.get("device_code"), user_id=user_id)
            or self.device_repo.get_by_name(data.get("device_name") or data.get("name"), user_id=user_id)
        )
        if not device or device.is_deleted:
            logger.warning("control_device: Device not found | data=%s", data)
            return {"success": False, "status": 404}
        if user_id is not None and device.user_id != user_id:
            return {"success": False, "status": 404}
        action = str(data.get("action") or data.get("value"))
        # ✅ Lấy numeric value riêng (ví dụ: bật đèn 100%)
        numeric_value = data.get("value")
        if numeric_value is not None:
            try:
                numeric_value = float(numeric_value)
            except Exception:
                numeric_value = None
        return self.send_command(device, action, source="API", numeric_value=numeric_value, user_id=user_id)

    def send_command(self, device, action: str, source: str = "API", numeric_value: Optional[float] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        try:
            status = self.status_repo.get_or_create_locked(device)
            logger.debug("[DEVICE COMMAND] user_id=%s device=%s(%d) action=%s value=%s source=%s",
                         user_id, device.code, device.id, action, numeric_value, source)
            action_text = str(action).strip()
            action_upper = action_text.upper()

            # Normalize common binary command variants from clients.
            if action_upper in ("1", "TRUE", "ON"):
                action_text = "ON"
                action_upper = "ON"
            elif action_upper in ("0", "FALSE", "OFF"):
                action_text = "OFF"
                action_upper = "OFF"

            # Nếu có numeric_value (brightness/speed/temp), gửi giá trị đó thay vì "ON"
            # ESP nhận số → set PWM/level rồi tự bật; nhận "OFF" → tắt
            if numeric_value is not None and action_upper != "OFF":
                mqtt_payload = str(int(numeric_value))
            else:
                mqtt_payload = action_text
            published = self.mqtt.send_device_command(device_code=device.code, payload=mqtt_payload)
            if not published:
                logger.error("[DEVICE ERROR] MQTT publish failed for device=%s payload=%s", device.code, mqtt_payload)
                db.session.rollback()
                return {"success": False, "status": 503, "message": "MQTT broker unavailable or publish failed"}

            # ✅ is_on logic: ON=True, OFF=False, SET_VALUE=True (đang chỉnh, không tắt)
            if action_upper == "ON":
                status.is_on = True
            elif action_upper == "OFF":
                status.is_on = False
            elif action_upper == "SET_VALUE":
                status.is_on = True  # SET_VALUE không tắt thiết bị
            else:
                try:
                    status.is_on = float(action) > 0
                except Exception:
                    status.is_on = True

            # ✅ Lưu numeric value vào DB nếu có
            if numeric_value is not None:
                status.value = str(numeric_value)
            else:
                status.value = action_text

            self.status_repo.save(status)
            self.log_repo.add(
                device_code=device.code,
                device_id=device.id,
                action=f"CONTROL: {action_text}",
                source=source,
                user_id=user_id,
            )
            db.session.commit()

            # ✅ Emit numeric value để frontend update slider — không emit 'ON'/'OFF' string
            emit_value = None
            try:
                v = float(status.value)
                if not v == 0 or action_upper not in ("ON", "OFF"):
                    emit_value = v
            except Exception:
                emit_value = None

            self.realtime.notify_device_status({
                "event": "DEVICE_UPDATED",
                "device_id": device.id,
                "device_code": device.code,
                "device_name": device.name,
                "is_on": status.is_on,
                "value": emit_value
            }, user_id=user_id)
            logger.info("[DEVICE SUCCESS] user_id=%s device=%s(%d) is_on=%s value=%s",
                        user_id, device.code, device.id, status.is_on, emit_value)
            return {"success": True}
        except Exception as e:
            logger.error("[DEVICE ERROR] user_id=%s device=%s action=%s | error: %s",
                         user_id, device.code if hasattr(device, 'code') else 'unknown', action, e, exc_info=True)
            db.session.rollback()
            return {"success": False, "status": 500}
