"""Tests for app.usecases.ai_usecase — AIUseCase helper methods and rule-mode logic."""
import pytest
from unittest.mock import MagicMock, patch

from app.usecases.ai_usecase import AIUseCase, _reply


# ---------------------------------------------------------------------------
# Module-level helper: _reply
# ---------------------------------------------------------------------------

class TestReply:
    def test_basic_reply(self):
        result = _reply("Hello")
        assert result["reply"] == "Hello"
        assert result["devices_changed"] is False
        assert result["controlled_devices"] == []

    def test_reply_with_controlled_devices(self):
        controlled = [{"code": "LIGHT01", "is_on": True, "value": None}]
        result = _reply("Done", controlled=controlled)
        assert result["devices_changed"] is True
        assert result["controlled_devices"] == controlled

    def test_reply_with_mood_data(self):
        result = _reply("OK", mood_data={"mood": "happy"})
        assert result["mood_data"] == {"mood": "happy"}

    def test_reply_without_mood_data_has_no_mood_key(self):
        result = _reply("No mood")
        assert "mood_data" not in result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_usecase(**kwargs):
    """Create AIUseCase with mocked dependencies."""
    defaults = dict(
        ai_service=MagicMock(),
        alert_usecase=MagicMock(),
        mqtt_publisher=MagicMock(),
        realtime_notifier=MagicMock(),
        device_usecase=MagicMock(),
        sensor_usecase=MagicMock(),
        room_usecase=MagicMock(),
    )
    defaults.update(kwargs)
    return AIUseCase(**defaults)


def _make_house():
    return {
        "devices": [
            {"id": 1, "name": "Light Bedroom", "code": "LIGHT01", "is_on": False,
             "value": None, "room_name": "Bedroom", "room_id": 1,
             "control_types": "switch", "category": "light", "icon": None},
            {"id": 2, "name": "Fan Kitchen", "code": "FAN01", "is_on": True,
             "value": "3", "room_name": "Kitchen", "room_id": 2,
             "control_types": "speed", "category": "fan", "icon": None},
            {"id": 3, "name": "Temp Sensor", "code": "SENSOR01", "is_on": True,
             "value": "32.0", "room_name": "Living", "room_id": 3,
             "control_types": "", "category": "sensor", "icon": None},
        ],
        "rooms": [
            {"id": 1, "name": "Bedroom", "device_names": ["Light Bedroom"]},
            {"id": 2, "name": "Kitchen", "device_names": ["Fan Kitchen"]},
            {"id": 3, "name": "Living", "device_names": ["Temp Sensor"]},
        ],
        "floors": [{"name": "Floor 1", "room_names": ["Bedroom", "Kitchen", "Living"]}],
    }


# ---------------------------------------------------------------------------
# _get_realtime_house
# ---------------------------------------------------------------------------

class TestGetRealtimeHouse:
    def test_returns_house_with_devices_from_context(self):
        uc = _make_usecase(device_usecase=None, room_usecase=None)
        context = _make_house()
        result = uc._get_realtime_house(context_data=context, user_id=1)
        assert "devices" in result
        assert "rooms" in result

    def test_caches_result(self):
        mock_device_uc = MagicMock()
        mock_device_uc.get_all_devices.return_value = []
        uc = _make_usecase(device_usecase=mock_device_uc, room_usecase=None)
        uc._get_realtime_house(user_id=42)
        uc._get_realtime_house(user_id=42)
        # Second call should use cache — get_all_devices called only once
        mock_device_uc.get_all_devices.assert_called_once()

    def test_no_device_usecase_returns_empty_devices(self):
        uc = _make_usecase(device_usecase=None, room_usecase=None)
        result = uc._get_realtime_house()
        assert result["devices"] == []

    def test_devices_as_dict_passed_through(self):
        mock_device_uc = MagicMock()
        mock_device_uc.get_all_devices.return_value = [
            {"id": 99, "name": "TestDev", "code": "T99", "is_on": True}
        ]
        uc = _make_usecase(device_usecase=mock_device_uc, room_usecase=None)
        result = uc._get_realtime_house()
        assert any(d["id"] == 99 for d in result["devices"])

    def test_device_orm_objects_converted(self):
        mock_device_uc = MagicMock()
        dev = MagicMock()
        dev.id = 5
        dev.name = "ORM Device"
        dev.code = "ORM01"
        dev.control_types = "switch"
        dev.category = "light"
        dev.icon = None
        status = MagicMock()
        status.is_on = True
        status.value = "ON"
        dev.status = status
        dev.room = MagicMock()
        dev.room.name = "Hall"
        dev.room.id = 7
        mock_device_uc.get_all_devices.return_value = [dev]
        uc = _make_usecase(device_usecase=mock_device_uc, room_usecase=None)
        result = uc._get_realtime_house()
        assert result["devices"][0]["name"] == "ORM Device"
        assert result["devices"][0]["is_on"] is True

    def test_rooms_from_room_usecase(self):
        mock_room_uc = MagicMock()
        mock_room_uc.get_all_rooms.return_value = [{"id": 9, "name": "Attic"}]
        uc = _make_usecase(device_usecase=None, room_usecase=mock_room_uc)
        result = uc._get_realtime_house()
        assert result["rooms"] == [{"id": 9, "name": "Attic"}]


# ---------------------------------------------------------------------------
# _find_devices_in_room
# ---------------------------------------------------------------------------

class TestFindDevicesInRoom:
    def test_returns_devices_in_named_room(self):
        uc = _make_usecase()
        house = _make_house()
        result = uc._find_devices_in_room(house, "Bedroom")
        assert len(result) == 1
        assert result[0]["code"] == "LIGHT01"

    def test_returns_empty_list_for_unknown_room(self):
        uc = _make_usecase()
        house = _make_house()
        result = uc._find_devices_in_room(house, "UnknownRoom")
        assert result == []

    def test_case_insensitive_room_name(self):
        uc = _make_usecase()
        house = _make_house()
        result = uc._find_devices_in_room(house, "bedroom")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _find_devices_by_category
# ---------------------------------------------------------------------------

class TestFindDevicesByCategory:
    def test_finds_lights(self):
        uc = _make_usecase()
        house = _make_house()
        result = uc._find_devices_by_category(house, "light")
        assert len(result) == 1
        assert result[0]["code"] == "LIGHT01"

    def test_finds_fans(self):
        uc = _make_usecase()
        house = _make_house()
        result = uc._find_devices_by_category(house, "fan")
        assert len(result) == 1
        assert result[0]["code"] == "FAN01"

    def test_sensors_excluded(self):
        uc = _make_usecase()
        house = _make_house()
        result = uc._find_devices_by_category(house, "sensor")
        assert result == []  # sensors excluded

    def test_scoped_to_room(self):
        uc = _make_usecase()
        house = _make_house()
        result = uc._find_devices_by_category(house, "light", room_name="Bedroom")
        assert len(result) == 1

    def test_scoped_to_wrong_room_returns_empty(self):
        uc = _make_usecase()
        house = _make_house()
        result = uc._find_devices_by_category(house, "light", room_name="Kitchen")
        assert result == []

    def test_find_by_type_alias(self):
        uc = _make_usecase()
        house = _make_house()
        # _find_devices_by_type should alias _find_devices_by_category
        r1 = uc._find_devices_by_type(house, "fan")
        r2 = uc._find_devices_by_category(house, "fan")
        assert r1 == r2

    def test_fan_alias_quat_only_in_mixed_room_dataset(self):
        """Regression: 'fan/quat' must not include unrelated sensors in same room."""
        uc = _make_usecase()
        house = {
            "devices": [
                {"id": 1, "name": "Quat", "code": "quat", "is_on": False,
                 "value": None, "room_name": "Kitchen", "room_id": 2,
                 "control_types": ["switch"], "category": "actuator", "icon": "🌀"},
                {"id": 2, "name": "Nhiet do", "code": "temperature", "is_on": True,
                 "value": "29", "room_name": "Kitchen", "room_id": 2,
                 "control_types": [], "category": "sensor", "icon": "🌡️"},
                {"id": 3, "name": "Do am", "code": "humidity", "is_on": True,
                 "value": "75", "room_name": "Kitchen", "room_id": 2,
                 "control_types": [], "category": "sensor", "icon": "💧"},
                {"id": 4, "name": "Anh sang", "code": "light", "is_on": True,
                 "value": "300", "room_name": "Kitchen", "room_id": 2,
                 "control_types": [], "category": "sensor", "icon": "🔆"},
            ],
            "rooms": [
                {"id": 2, "name": "Kitchen", "device_names": ["Quat", "Nhiet do", "Do am", "Anh sang"]},
            ],
            "floors": [],
        }

        result = uc._find_devices_by_category(house, "fan", room_name="Kitchen")
        assert [d["code"] for d in result] == ["quat"]

    def test_ac_does_not_match_actuator_substring(self):
        """Regression: token 'ac' must not match category 'actuator' by substring."""
        uc = _make_usecase()
        house = {
            "devices": [
                {"id": 1, "name": "Quat", "code": "quat", "is_on": False,
                 "value": None, "room_name": "Kitchen", "room_id": 2,
                 "control_types": ["switch"], "category": "actuator", "icon": "🌀"},
                {"id": 2, "name": "Nhiet do", "code": "nhiet_do", "is_on": False,
                 "value": None, "room_name": "Kitchen", "room_id": 2,
                 "control_types": ["switch"], "category": "actuator", "icon": "🌡️"},
            ],
            "rooms": [
                {"id": 2, "name": "Kitchen", "device_names": ["Quat", "Nhiet do"]},
            ],
            "floors": [],
        }

        result = uc._find_devices_by_category(house, "ac", room_name="Kitchen")
        assert result == []


# ---------------------------------------------------------------------------
# _execute_plan
# ---------------------------------------------------------------------------

class TestExecutePlan:
    def test_empty_plan_returns_empty(self):
        uc = _make_usecase()
        results, controlled = uc._execute_plan([])
        assert results == []
        assert controlled == []

    def test_successful_command(self):
        mock_device_uc = MagicMock()
        mock_device_uc.control_device.return_value = {"success": True}
        uc = _make_usecase(device_usecase=mock_device_uc)
        plan = [{"dev": {"code": "LIGHT01", "name": "Light"}, "action": "ON", "value": None, "msg": "bật đèn"}]
        results, controlled = uc._execute_plan(plan)
        assert "bật đèn" in results
        assert controlled[0]["is_on"] is True

    def test_failed_command_not_in_results(self):
        mock_device_uc = MagicMock()
        mock_device_uc.control_device.return_value = {"success": False}
        uc = _make_usecase(device_usecase=mock_device_uc)
        plan = [{"dev": {"code": "LIGHT01", "name": "Light"}, "action": "ON", "value": None}]
        results, controlled = uc._execute_plan(plan)
        assert results == []
        assert controlled == []

    def test_value_passed_to_control_device(self):
        mock_device_uc = MagicMock()
        mock_device_uc.control_device.return_value = {"success": True}
        uc = _make_usecase(device_usecase=mock_device_uc)
        plan = [{"dev": {"code": "FAN01", "name": "Fan"}, "action": "SET", "value": "3", "msg": "set fan"}]
        results, controlled = uc._execute_plan(plan)
        call_args = mock_device_uc.control_device.call_args[0][0]
        assert call_args["value"] == 3.0

    def test_duplicate_messages_deduplicated(self):
        mock_device_uc = MagicMock()
        mock_device_uc.control_device.return_value = {"success": True}
        uc = _make_usecase(device_usecase=mock_device_uc)
        plan = [
            {"dev": {"code": "L1", "name": "L1"}, "action": "ON", "value": None, "msg": "same msg"},
            {"dev": {"code": "L2", "name": "L2"}, "action": "ON", "value": None, "msg": "same msg"},
        ]
        results, _ = uc._execute_plan(plan)
        assert results.count("same msg") == 1

    def test_no_device_usecase_returns_empty(self):
        uc = _make_usecase(device_usecase=None)
        plan = [{"dev": {"code": "X", "name": "X"}, "action": "ON", "value": None}]
        results, controlled = uc._execute_plan(plan)
        assert results == []
        assert controlled == []


# ---------------------------------------------------------------------------
# handle_chat — rule mode FAQ
# ---------------------------------------------------------------------------

class TestHandleChatRuleFaq:
    def _uc_with_empty_house(self):
        uc = _make_usecase(device_usecase=None, room_usecase=None)
        return uc

    def test_greet_returns_reply(self):
        uc = self._uc_with_empty_house()
        result = uc.handle_chat("xin chào", mode="rule")
        assert "Alfred" in result["reply"] or "Kính chào" in result["reply"]

    def test_help_command(self):
        uc = self._uc_with_empty_house()
        result = uc.handle_chat("/help", mode="rule")
        assert result["reply"]  # non-empty

    def test_time_query(self):
        uc = self._uc_with_empty_house()
        result = uc.handle_chat("mấy giờ rồi", mode="rule")
        # Should contain time/date digits
        import re
        assert re.search(r"\d{2}:\d{2}", result["reply"])

    def test_thank_you(self):
        uc = self._uc_with_empty_house()
        result = uc.handle_chat("cảm ơn nhé", mode="rule")
        assert result["reply"]

    def test_who_are_you(self):
        uc = self._uc_with_empty_house()
        result = uc.handle_chat("bạn là ai vậy", mode="rule")
        assert "Alfred" in result["reply"]

    def test_weather_in_rule_mode(self):
        uc = self._uc_with_empty_house()
        result = uc.handle_chat("thời tiết hôm nay thế nào", mode="rule")
        assert result["reply"]


# ---------------------------------------------------------------------------
# handle_chat — rule mode device control
# ---------------------------------------------------------------------------

class TestHandleChatRuleControl:
    def test_no_devices_unknown_message(self):
        uc = _make_usecase(device_usecase=None, room_usecase=None)
        result = uc.handle_chat("bật đèn phòng ngủ", mode="rule")
        # No devices → some fallback response
        assert isinstance(result["reply"], str)

    def test_turn_on_device_success(self):
        mock_device_uc = MagicMock()
        mock_device_uc.get_all_devices.return_value = []
        mock_device_uc.get_all_active.side_effect = AttributeError
        mock_device_uc.get_all.side_effect = AttributeError
        mock_device_uc.control_device.return_value = {"success": True}
        mock_room_uc = MagicMock()
        mock_room_uc.get_all_rooms.return_value = []
        uc = AIUseCase(
            ai_service=MagicMock(),
            alert_usecase=MagicMock(),
            mqtt_publisher=MagicMock(),
            realtime_notifier=MagicMock(),
            device_usecase=mock_device_uc,
            room_usecase=mock_room_uc,
        )
        result = uc.handle_chat("bật đèn", mode="rule")
        assert isinstance(result["reply"], str)


class TestSmartClarificationFallback:
    def test_rule_mode_unknown_message_gives_smart_hint_vi(self):
        uc = _make_usecase(device_usecase=None, room_usecase=None)
        house = {
            "devices": [
                {"id": 1, "name": "Den bep", "code": "LIGHT_KITCHEN", "is_on": False,
                 "value": None, "room_name": "Kitchen", "room_id": 1,
                 "control_types": ["switch"], "category": "light", "icon": None},
            ],
            "rooms": [{"id": 1, "name": "Kitchen", "device_names": ["Den bep"]}],
            "floors": [],
        }
        with patch.object(uc, "_get_realtime_house", return_value=house):
            result = uc.handle_chat("aloalo xyz", mode="rule", language="vi")
        assert "Ngài có thể nói" in result["reply"]
        assert "Kitchen" in result["reply"]

    def test_rule_mode_unknown_message_gives_smart_hint_en(self):
        uc = _make_usecase(device_usecase=None, room_usecase=None)
        house = {
            "devices": [
                {"id": 1, "name": "Kitchen Light", "code": "LIGHT_KITCHEN", "is_on": False,
                 "value": None, "room_name": "Kitchen", "room_id": 1,
                 "control_types": ["switch"], "category": "light", "icon": None},
            ],
            "rooms": [{"id": 1, "name": "Kitchen", "device_names": ["Kitchen Light"]}],
            "floors": [],
        }
        with patch.object(uc, "_get_realtime_house", return_value=house):
            result = uc.handle_chat("some random text", mode="rule", language="en")
        assert "Try one of these" in result["reply"]
        assert "Kitchen" in result["reply"]


class TestHandleChatOwnerRoomAndScenario:
    def test_where_am_i_accepts_owner_room_object(self):
        uc = _make_usecase(device_usecase=None, room_usecase=None)
        house = {
            "devices": [],
            "rooms": [
                {"id": 1, "name": "Bedroom", "device_names": []},
                {"id": 2, "name": "Kitchen", "device_names": []},
            ],
            "floors": [],
        }
        with patch.object(uc, "_get_realtime_house", return_value=house):
            result = uc.handle_chat(
                "tôi đang ở đâu",
                context_data={"owner_room": {"id": 2, "name": "Kitchen"}},
                mode="rule",
            )
        assert "Kitchen" in result["reply"]

    def test_dark_scenario_uses_owner_room_without_asking(self):
        mock_device_uc = MagicMock()
        mock_device_uc.control_device.return_value = {"success": True}
        uc = _make_usecase(device_usecase=mock_device_uc)
        house = {
            "devices": [
                {"id": 1, "name": "Light Bedroom", "code": "L1", "is_on": False,
                 "value": None, "room_name": "Bedroom", "room_id": 1,
                 "control_types": ["switch"], "category": "light", "icon": None},
                {"id": 2, "name": "Light Kitchen", "code": "L2", "is_on": False,
                 "value": None, "room_name": "Kitchen", "room_id": 2,
                 "control_types": ["switch"], "category": "light", "icon": None},
            ],
            "rooms": [
                {"id": 1, "name": "Bedroom", "device_names": ["Light Bedroom"]},
                {"id": 2, "name": "Kitchen", "device_names": ["Light Kitchen"]},
            ],
            "floors": [],
        }
        with patch.object(uc, "_get_realtime_house", return_value=house):
            result = uc.handle_chat(
                "tối quá",
                context_data={"owner_room": {"id": 2, "name": "Kitchen"}},
                mode="rule",
            )

        assert "ở phòng nào" not in result["reply"].lower()
        assert result["devices_changed"] is True
        assert any(d["code"] == "L2" for d in result["controlled_devices"])

    def test_hot_scenario_uses_device_room_name_when_room_device_names_missing(self):
        mock_device_uc = MagicMock()
        mock_device_uc.control_device.return_value = {"success": True}
        uc = _make_usecase(device_usecase=mock_device_uc)
        house = {
            "devices": [
                {"id": 1, "name": "AC Bedroom", "code": "AC1", "is_on": False,
                 "value": None, "room_name": "Bedroom", "room_id": 1,
                 "control_types": ["switch"], "category": "ac", "icon": None},
                {"id": 2, "name": "AC Kitchen", "code": "AC2", "is_on": False,
                 "value": None, "room_name": "Kitchen", "room_id": 2,
                 "control_types": ["switch"], "category": "ac", "icon": None},
            ],
            # device_names intentionally mismatched to validate fallback by device.room_name
            "rooms": [
                {"id": 1, "name": "Bedroom", "device_names": ["Unknown 1"]},
                {"id": 2, "name": "Kitchen", "device_names": ["Unknown 2"]},
            ],
            "floors": [],
        }
        with patch.object(uc, "_get_realtime_house", return_value=house):
            result = uc.handle_chat(
                "nóng quá",
                context_data={"owner_room": {"id": 2, "name": "Kitchen"}},
                mode="rule",
            )

        assert "ở phòng nào" not in result["reply"].lower()
        assert result["devices_changed"] is True
        assert any(d["code"] == "AC2" for d in result["controlled_devices"])

    def test_dark_scenario_multi_room_confirm_requires_room_vi(self):
        mock_device_uc = MagicMock()
        mock_device_uc.control_device.return_value = {"success": True}
        uc = _make_usecase(device_usecase=mock_device_uc)
        house = {
            "devices": [
                {"id": 1, "name": "Light Bedroom", "code": "L1", "is_on": False,
                 "value": None, "room_name": "Bedroom", "room_id": 1,
                 "control_types": ["switch"], "category": "light", "icon": None},
                {"id": 2, "name": "Light Kitchen", "code": "L2", "is_on": False,
                 "value": None, "room_name": "Kitchen", "room_id": 2,
                 "control_types": ["switch"], "category": "light", "icon": None},
            ],
            "rooms": [
                {"id": 1, "name": "Bedroom", "device_names": ["Light Bedroom"]},
                {"id": 2, "name": "Kitchen", "device_names": ["Light Kitchen"]},
            ],
            "floors": [],
        }
        with patch.object(uc, "_get_realtime_house", return_value=house):
            first = uc.handle_chat("tối quá", mode="rule")
            second = uc.handle_chat("ok làm đi", mode="rule")

        assert "ở phòng nào" in first["reply"].lower()
        assert "ở phòng nào" in second["reply"].lower()
        assert second["devices_changed"] is False

    def test_dark_scenario_multi_room_confirm_requires_room_en(self):
        mock_device_uc = MagicMock()
        mock_device_uc.control_device.return_value = {"success": True}
        uc = _make_usecase(device_usecase=mock_device_uc)
        house = {
            "devices": [
                {"id": 1, "name": "Light Bedroom", "code": "L1", "is_on": False,
                 "value": None, "room_name": "Bedroom", "room_id": 1,
                 "control_types": ["switch"], "category": "light", "icon": None},
                {"id": 2, "name": "Light Kitchen", "code": "L2", "is_on": False,
                 "value": None, "room_name": "Kitchen", "room_id": 2,
                 "control_types": ["switch"], "category": "light", "icon": None},
            ],
            "rooms": [
                {"id": 1, "name": "Bedroom", "device_names": ["Light Bedroom"]},
                {"id": 2, "name": "Kitchen", "device_names": ["Light Kitchen"]},
            ],
            "floors": [],
        }
        with patch.object(uc, "_get_realtime_house", return_value=house):
            first = uc.handle_chat("too dark", mode="rule", language="en")
            second = uc.handle_chat("confirm", mode="rule", language="en")

        assert "which room" in first["reply"].lower()
        assert "which room" in second["reply"].lower()
        assert second["devices_changed"] is False
