"""Unit tests for DeviceUseCase — covers create, get, delete, control, update_status."""
from unittest.mock import MagicMock, patch
import pytest

from app.usecases.device_usecase import DeviceUseCase


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_device(id=1, name="Light", code="den", user_id=1, is_deleted=False):
    d = MagicMock()
    d.id = id
    d.name = name
    d.code = code
    d.icon = "💡"
    d.category = "light"
    d.room_id = None
    d.map_x = None
    d.map_y = None
    d.user_id = user_id
    d.is_deleted = is_deleted
    d.types_list = ["switch"]
    d.room = None
    d.status = _make_status()
    return d


def _make_status(is_on=False, value="OFF"):
    s = MagicMock()
    s.is_on = is_on
    s.value = value
    return s


def _make_usecase():
    device_repo = MagicMock()
    status_repo = MagicMock()
    log_repo = MagicMock()
    mqtt = MagicMock()
    realtime = MagicMock()
    uc = DeviceUseCase(device_repo, status_repo, log_repo, mqtt, realtime)
    return uc, device_repo, status_repo, log_repo, mqtt, realtime


# ──────────────────────────────────────────────
# get_all_devices
# ──────────────────────────────────────────────

def test_get_all_devices_empty():
    uc, repo, *_ = _make_usecase()
    repo.get_all_active.return_value = []
    assert uc.get_all_devices(user_id=1) == []


def test_get_all_devices_returns_list():
    uc, repo, *_ = _make_usecase()
    repo.get_all_active.return_value = [_make_device()]
    result = uc.get_all_devices(user_id=1)
    assert len(result) == 1
    assert result[0]["name"] == "Light"
    assert result[0]["code"] == "den"
    assert result[0]["is_on"] is False


def test_get_all_devices_numeric_value():
    uc, repo, *_ = _make_usecase()
    dev = _make_device()
    dev.status.value = "75.5"
    repo.get_all_active.return_value = [dev]
    result = uc.get_all_devices(user_id=1)
    assert result[0]["value"] == 75.5


def test_get_all_devices_non_numeric_value():
    uc, repo, *_ = _make_usecase()
    dev = _make_device()
    dev.status.value = "ON"
    repo.get_all_active.return_value = [dev]
    result = uc.get_all_devices(user_id=1)
    assert result[0]["value"] == "ON"


def test_get_all_devices_no_status():
    uc, repo, *_ = _make_usecase()
    dev = _make_device()
    dev.status = None
    repo.get_all_active.return_value = [dev]
    result = uc.get_all_devices(user_id=1)
    assert result[0]["is_on"] is False
    assert result[0]["value"] == "OFF"


# ──────────────────────────────────────────────
# create_device
# ──────────────────────────────────────────────

def test_create_device_success():
    uc, repo, status_repo, log_repo, mqtt, realtime = _make_usecase()
    repo.exists_by_name.return_value = False
    repo.exists_by_code.return_value = False
    created = _make_device(id=5, name="Fan", code="quat")
    repo.create.return_value = created

    with patch("app.usecases.device_usecase.db") as mock_db:
        result = uc.create_device({"name": "Fan", "code": "quat"}, user_id=1)

    assert result["success"] is True
    assert result["name"] == "Fan"
    assert result["code"] == "quat"


def test_create_device_empty_name():
    uc, *_ = _make_usecase()
    result = uc.create_device({"name": ""}, user_id=1)
    assert result["success"] is False
    assert result["status"] == 400


def test_create_device_auto_suffix_name():
    uc, repo, status_repo, log_repo, mqtt, realtime = _make_usecase()
    repo.exists_by_name.side_effect = [True, False]
    repo.exists_by_code.return_value = False
    created = _make_device(id=6, name="Light 2", code="light_2")
    repo.create.return_value = created

    with patch("app.usecases.device_usecase.db"):
        result = uc.create_device({"name": "Light"}, user_id=1)

    assert result["success"] is True
    assert result["name"] == "Light 2"


def test_create_device_auto_suffix_code():
    uc, repo, status_repo, log_repo, mqtt, realtime = _make_usecase()
    repo.exists_by_name.return_value = False
    repo.exists_by_code.side_effect = [True, False]
    created = _make_device(id=7, name="Den", code="den_2")
    repo.create.return_value = created

    with patch("app.usecases.device_usecase.db"):
        result = uc.create_device({"name": "Den", "code": "den"}, user_id=1)

    assert result["success"] is True
    assert result["code"] == "den_2"


# ──────────────────────────────────────────────
# delete_device
# ──────────────────────────────────────────────

def test_delete_device_success():
    uc, repo, status_repo, *_ = _make_usecase()
    dev = _make_device()
    repo.get_by_code.return_value = dev

    with patch("app.usecases.device_usecase.db"):
        result = uc.delete_device("Light", user_id=1)

    assert result["success"] is True
    repo.delete.assert_called_once_with(dev)


def test_delete_device_not_found():
    uc, repo, *_ = _make_usecase()
    repo.get_by_name.return_value = None
    result = uc.delete_device("nonexistent", user_id=1)
    assert result["success"] is False
    assert result["status"] == 404


def test_delete_already_deleted():
    uc, repo, *_ = _make_usecase()
    dev = _make_device(is_deleted=True)
    repo.get_by_name.return_value = dev
    result = uc.delete_device("Light", user_id=1)
    assert result["success"] is False
    assert result["status"] == 404


# ──────────────────────────────────────────────
# control_device
# ──────────────────────────────────────────────

def test_control_device_not_found():
    uc, repo, *_ = _make_usecase()
    repo.get_by_id.return_value = None
    repo.get_by_code.return_value = None
    repo.get_by_name.return_value = None
    result = uc.control_device({"device_code": "zzz"}, user_id=1)
    assert result["success"] is False
    assert result["status"] == 404


def test_control_device_wrong_user():
    uc, repo, *_ = _make_usecase()
    dev = _make_device(user_id=2)
    repo.get_by_id.return_value = None
    repo.get_by_code.return_value = dev
    repo.get_by_name.return_value = None
    result = uc.control_device({"device_code": "den"}, user_id=1)
    assert result["success"] is False
    assert result["status"] == 404


def test_control_device_on():
    uc, repo, status_repo, log_repo, mqtt, realtime = _make_usecase()
    dev = _make_device()
    repo.get_by_id.return_value = None
    repo.get_by_code.return_value = dev
    repo.get_by_name.return_value = None
    status = _make_status()
    status_repo.get_or_create_locked.return_value = status

    with patch("app.usecases.device_usecase.db"):
        result = uc.control_device({"device_code": "den", "action": "ON"}, user_id=1)

    assert result["success"] is True
    assert status.is_on is True
    mqtt.send_device_command.assert_called_once_with(device_code="den", payload="ON")


def test_control_device_off():
    uc, repo, status_repo, log_repo, mqtt, realtime = _make_usecase()
    dev = _make_device()
    repo.get_by_id.return_value = None
    repo.get_by_code.return_value = dev
    repo.get_by_name.return_value = None
    status = _make_status(is_on=True, value="ON")
    status_repo.get_or_create_locked.return_value = status

    with patch("app.usecases.device_usecase.db"):
        result = uc.control_device({"device_code": "den", "action": "OFF"}, user_id=1)

    assert result["success"] is True
    assert status.is_on is False


def test_control_device_numeric_value():
    uc, repo, status_repo, log_repo, mqtt, realtime = _make_usecase()
    dev = _make_device()
    repo.get_by_id.return_value = None
    repo.get_by_code.return_value = dev
    repo.get_by_name.return_value = None
    status = _make_status()
    status_repo.get_or_create_locked.return_value = status

    with patch("app.usecases.device_usecase.db"):
        result = uc.control_device({"device_code": "den", "action": "SET_VALUE", "value": 75}, user_id=1)

    assert result["success"] is True
    mqtt.send_device_command.assert_called_once_with(device_code="den", payload="75")


# ──────────────────────────────────────────────
# update_device_status (MQTT path)
# ──────────────────────────────────────────────

def test_update_device_status_on():
    uc, repo, status_repo, log_repo, *_ = _make_usecase()
    dev = _make_device()
    # No user_id => MQTT path uses get_all_by_code
    repo.get_all_by_code.return_value = [dev]
    status = _make_status()
    status_repo.get_or_create.return_value = status

    with patch("app.usecases.device_usecase.db"):
        uc.update_device_status("den", "ON", source="MQTT")

    assert status.is_on is True
    assert status.value == "ON"


def test_update_device_status_unknown_device():
    uc, repo, *_ = _make_usecase()
    # No user_id => MQTT path uses get_all_by_code
    repo.get_all_by_code.return_value = []
    # Should not raise
    with patch("app.usecases.device_usecase.db"):
        uc.update_device_status("unknown_code", "ON")


# ──────────────────────────────────────────────
# update_device_coords
# ──────────────────────────────────────────────

def test_update_coords_success():
    uc, repo, *_ = _make_usecase()
    dev = _make_device()
    repo.get_by_id.return_value = dev
    repo.get_by_name.return_value = None

    with patch("app.usecases.device_usecase.db"):
        result = uc.update_device_coords({"id": 1, "map_x": 0.5, "map_y": 0.3}, user_id=1)

    assert result["success"] is True
    assert dev.map_x == 0.5
    assert dev.map_y == 0.3


def test_update_coords_not_found():
    uc, repo, *_ = _make_usecase()
    repo.get_by_id.return_value = None
    repo.get_by_name.return_value = None
    result = uc.update_device_coords({"id": 999}, user_id=1)
    assert result["success"] is False
    assert result["status"] == 404
