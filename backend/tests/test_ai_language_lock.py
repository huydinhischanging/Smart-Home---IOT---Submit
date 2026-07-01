import re
from dataclasses import dataclass
from importlib import util
from pathlib import Path

_ai_path = Path(__file__).resolve().parents[1] / "app" / "usecases" / "ai_usecase.py"
_spec = util.spec_from_file_location("ai_usecase_local", _ai_path)
_module = util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_module)
AIUseCase = _module.AIUseCase


class FakeAIService:
    def parse_intent(self, message: str):
        lowered = message.lower()
        if "multi lights" in lowered or "nhiều đèn" in lowered:
            return {
                "intent": "control",
                "action": "on",
                "device_type": "light",
                "room": None,
                "floor": None,
                "reply": None,
            }
        if "add device" in lowered:
            return {
                "intent": "add",
                "device_name_raw": "Lamp X",
                "device_name": "lamp x",
                "device_type": "light",
                "room": "Kitchen",
            }
        if "thêm thiết bị" in lowered or "them thiet bi" in lowered:
            return {
                "intent": "add",
                "device_name_raw": "Đèn X",
                "device_name": "đèn x",
                "device_type": "light",
                "room": "Kitchen",
            }
        return {"intent": "chat", "reply": None}

    def ask_alfred(self, message: str, house_context=None, preferred_language: str = "auto"):
        return "Fallback reply"


class FakeRealtime:
    def notify_ai_reply(self, payload):
        return None

    def notify_device_list_changed(self):
        return None


@dataclass
class FakeDeviceUsecase:
    devices: list

    def get_all_devices(self, user_id=None):
        return self.devices

    def control_device(self, payload):
        code = payload.get("device_code")
        action = payload.get("action")
        for device in self.devices:
            if device.get("code") == code:
                device["is_on"] = action != "OFF"
                return {"success": True}
        return {"success": False}

    def create_device(self, payload):
        name = payload["name"]
        code = name.lower().replace(" ", "_")
        self.devices.append({
            "id": len(self.devices) + 1,
            "name": name,
            "code": code,
            "category": payload.get("category", "other"),
            "is_on": False,
        })
        return {"success": True, "name": name, "code": code}

    def delete_device(self, name):
        before = len(self.devices)
        self.devices = [device for device in self.devices if device.get("name") != name]
        return {"success": len(self.devices) < before}


class Dummy:
    pass


def _make_usecase():
    devices = [
        {"id": 1, "name": "Bedroom Light", "code": "light_bed", "category": "light", "is_on": False},
        {"id": 2, "name": "Kitchen Light", "code": "light_kitchen", "category": "light", "is_on": False},
    ]
    return AIUseCase(
        ai_service=FakeAIService(),
        alert_usecase=Dummy(),
        mqtt_publisher=Dummy(),
        realtime_notifier=FakeRealtime(),
        device_usecase=FakeDeviceUsecase(devices),
        sensor_usecase=None,
        room_usecase=None,
        alfred_ai_service=None,
    )


def _context():
    return {
        "rooms": [
            {"id": 1, "name": "Bedroom", "floor": "Floor 1", "device_names": ["Bedroom Light"]},
            {"id": 2, "name": "Kitchen", "floor": "Floor 1", "device_names": ["Kitchen Light"]},
        ],
        "floors": [{"id": "f1", "name": "Floor 1", "room_names": ["Bedroom", "Kitchen"]}],
        "owner_room": "Kitchen",
    }


def _has_vietnamese_leak(reply: str) -> bool:
    markers = ["thưa", "ngài", "phòng", "đã ", "không", "hủy", "tôi "]
    lowered = reply.lower()
    return any(marker in lowered for marker in markers)


def _has_english_leak(reply: str) -> bool:
    patterns = [
        r"\bsir\b",
        r"\bturn on\b",
        r"\bturn off\b",
        r"\bcompleted\b",
        r"\bdevice\b",
        r"\bgood morning\b|\bgood afternoon\b|\bgood evening\b",
        r"\broom\s+[a-z0-9_]",
    ]
    lowered = reply.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)


class TestAiLanguageLockEnglish:
    def test_greeting_is_english_only(self):
        result = _make_usecase().handle_chat("hi", context_data=_context(), mode="llm", language="en", user_id=1)
        assert "Good" in result["reply"]
        assert not _has_vietnamese_leak(result["reply"])

    def test_pending_confirm_is_english_only(self):
        uc = _make_usecase()
        uc._set_pending_action({
            "plan": [{
                "dev": uc.device_usecase.devices[0],
                "action": "ON",
                "value": None,
                "room": "Bedroom",
                "msg": "turn on Bedroom Light",
            }],
            "need_room": False,
        }, user_id=1)
        result = uc.handle_chat("confirm", context_data=_context(), mode="llm", language="en", user_id=1)
        assert "completed" in result["reply"].lower()
        assert not _has_vietnamese_leak(result["reply"])

    def test_pending_room_selection_is_english_only(self):
        uc = _make_usecase()
        uc._set_pending_action({
            "plan": [
                {"dev": uc.device_usecase.devices[0], "action": "OFF", "value": None, "room": "Bedroom", "msg": "turn off Bedroom Light"},
                {"dev": uc.device_usecase.devices[1], "action": "OFF", "value": None, "room": "Kitchen", "msg": "turn off Kitchen Light"},
            ],
            "need_room": True,
        }, user_id=1)
        result = uc.handle_chat("kitchen", context_data=_context(), mode="llm", language="en", user_id=1)
        assert "room kitchen" in result["reply"].lower()
        assert not _has_vietnamese_leak(result["reply"])

    def test_owner_room_control_is_english_only(self):
        result = _make_usecase().handle_chat("multi lights please", context_data=_context(), mode="llm", language="en", user_id=1)
        assert "turned on" in result["reply"].lower()
        assert not _has_vietnamese_leak(result["reply"])

    def test_add_device_is_english_only(self):
        result = _make_usecase().handle_chat("add device now", context_data=_context(), mode="llm", language="en", user_id=1)
        assert "was added" in result["reply"].lower()
        assert not _has_vietnamese_leak(result["reply"])


class TestAiLanguageLockVietnamese:
    def test_greeting_is_vietnamese_only(self):
        result = _make_usecase().handle_chat("xin chào", context_data=_context(), mode="llm", language="vi", user_id=2)
        assert "Chào" in result["reply"]
        assert not _has_english_leak(result["reply"])

    def test_pending_confirm_is_vietnamese_only(self):
        uc = _make_usecase()
        uc._set_pending_action({
            "plan": [{
                "dev": uc.device_usecase.devices[0],
                "action": "ON",
                "value": None,
                "room": "Bedroom",
                "msg": "bật Bedroom Light",
            }],
            "need_room": False,
        }, user_id=2)
        result = uc.handle_chat("làm đi", context_data=_context(), mode="llm", language="vi", user_id=2)
        assert "đã thực hiện" in result["reply"].lower()
        assert not _has_english_leak(result["reply"])

    def test_pending_room_selection_is_vietnamese_only(self):
        uc = _make_usecase()
        uc._set_pending_action({
            "plan": [
                {"dev": uc.device_usecase.devices[0], "action": "OFF", "value": None, "room": "Bedroom", "msg": "tắt Bedroom Light"},
                {"dev": uc.device_usecase.devices[1], "action": "OFF", "value": None, "room": "Kitchen", "msg": "tắt Kitchen Light"},
            ],
            "need_room": True,
        }, user_id=2)
        result = uc.handle_chat("kitchen", context_data=_context(), mode="llm", language="vi", user_id=2)
        assert "phòng kitchen" in result["reply"].lower()
        assert not _has_english_leak(result["reply"])

    def test_owner_room_control_is_vietnamese_only(self):
        result = _make_usecase().handle_chat("nhiều đèn", context_data=_context(), mode="llm", language="vi", user_id=2)
        assert "đã bật" in result["reply"].lower()
        assert not _has_english_leak(result["reply"])

    def test_add_device_is_vietnamese_only(self):
        result = _make_usecase().handle_chat("thêm thiết bị", context_data=_context(), mode="llm", language="vi", user_id=2)
        assert "đã thêm thiết bị" in result["reply"].lower()
        assert not _has_english_leak(result["reply"])