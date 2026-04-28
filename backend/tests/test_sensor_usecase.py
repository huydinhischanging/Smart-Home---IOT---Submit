"""Tests for SensorUseCase — covers get_latest_data, get_latest_readings, handle_sensor_data."""
from unittest.mock import MagicMock, patch, call
import pytest
from flask import Flask

from app.extensions.database import db
from app.usecases.sensor_usecase import SensorUseCase


def _make_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    db.init_app(app)
    return app


def _make_usecase(**overrides):
    defaults = {
        "device_repo": MagicMock(),
        "status_repo": MagicMock(),
        "sensor_repo": MagicMock(),
        "alert_repo": MagicMock(),
        "realtime_notifier": MagicMock(),
        "ai_usecase": None,
    }
    defaults.update(overrides)
    return SensorUseCase(**defaults)


# ---------------------------------------------------------------------------
# get_latest_data
# ---------------------------------------------------------------------------

class TestGetLatestData:
    def test_returns_empty_when_no_statuses(self):
        uc = _make_usecase()
        uc.status_repo.get_all.return_value = []
        result = uc.get_latest_data()
        assert result == {}

    def test_numeric_values_included(self):
        uc = _make_usecase()
        status = MagicMock()
        status.value = "25.5"
        status.device.code = "temp_sensor"
        uc.status_repo.get_all.return_value = [status]
        result = uc.get_latest_data()
        assert result["temp_sensor"] == 25.5

    def test_non_numeric_values_excluded(self):
        uc = _make_usecase()
        status = MagicMock()
        status.value = "DETECTED"
        status.device.code = "pir"
        uc.status_repo.get_all.return_value = [status]
        result = uc.get_latest_data()
        assert "pir" not in result

    def test_multiple_sensors(self):
        uc = _make_usecase()
        s1 = MagicMock(); s1.value = "22.0"; s1.device.code = "temp"
        s2 = MagicMock(); s2.value = "60.0"; s2.device.code = "humidity"
        uc.status_repo.get_all.return_value = [s1, s2]
        result = uc.get_latest_data()
        assert len(result) == 2
        assert result["temp"] == 22.0
        assert result["humidity"] == 60.0

    def test_exception_returns_empty_dict(self):
        uc = _make_usecase()
        uc.status_repo.get_all.side_effect = Exception("DB error")
        result = uc.get_latest_data()
        assert result == {}


# ---------------------------------------------------------------------------
# get_latest_readings
# ---------------------------------------------------------------------------

class TestGetLatestReadings:
    def test_returns_expected_keys(self):
        uc = _make_usecase()
        uc.status_repo.get_all.return_value = []
        result = uc.get_latest_readings()
        assert "room_temp" in result
        assert "humidity" in result
        assert "light_level" in result

    def test_maps_room_temp(self):
        uc = _make_usecase()
        s = MagicMock(); s.value = "23.0"; s.device.code = "room_temp"
        uc.status_repo.get_all.return_value = [s]
        result = uc.get_latest_readings()
        assert result["room_temp"] == 23.0

    def test_maps_humidity(self):
        uc = _make_usecase()
        s = MagicMock(); s.value = "55.0"; s.device.code = "humidity"
        uc.status_repo.get_all.return_value = [s]
        result = uc.get_latest_readings()
        assert result["humidity"] == 55.0

    def test_fallback_temp_key(self):
        uc = _make_usecase()
        s = MagicMock(); s.value = "21.0"; s.device.code = "temp"
        uc.status_repo.get_all.return_value = [s]
        result = uc.get_latest_readings()
        assert result["room_temp"] == 21.0

    def test_none_when_no_sensor(self):
        uc = _make_usecase()
        uc.status_repo.get_all.return_value = []
        result = uc.get_latest_readings()
        assert result["room_temp"] is None
        assert result["humidity"] is None


# ---------------------------------------------------------------------------
# handle_sensor_data
# ---------------------------------------------------------------------------

@pytest.fixture
def app_ctx():
    app = _make_app()
    with app.app_context():
        db.create_all()
        yield


class TestHandleSensorData:
    def test_returns_false_for_unknown_device(self, app_ctx):
        uc = _make_usecase()
        uc.device_repo.get_all_by_code.return_value = []
        result = uc.handle_sensor_data("unknown_sensor", 25.5)
        assert result is False

    def test_numeric_sensor_data_saved(self, app_ctx):
        uc = _make_usecase()
        device = MagicMock(); device.is_deleted = False; device.id = 1; device.code = "temp"
        status = MagicMock()
        uc.device_repo.get_all_by_code.return_value = [device]
        uc.status_repo.get_or_create.return_value = status

        with patch.object(uc, "check_sensor_alert", return_value=None):
            result = uc.handle_sensor_data("temp", 23.5)

        assert result is True
        uc.sensor_repo.save.assert_called_once_with(1, 23.5)

    def test_pir_detected_sets_is_on_true(self, app_ctx):
        uc = _make_usecase()
        device = MagicMock(); device.is_deleted = False; device.id = 2; device.code = "pir"
        status = MagicMock()
        uc.device_repo.get_all_by_code.return_value = [device]
        uc.status_repo.get_or_create.return_value = status

        with patch.object(uc, "check_sensor_alert", return_value=None):
            result = uc.handle_sensor_data("pir", "DETECTED")

        assert result is True
        assert status.is_on is True

    def test_pir_clear_sets_is_on_false(self, app_ctx):
        uc = _make_usecase()
        device = MagicMock(); device.is_deleted = False; device.id = 2; device.code = "pir"
        status = MagicMock()
        uc.device_repo.get_all_by_code.return_value = [device]
        uc.status_repo.get_or_create.return_value = status

        with patch.object(uc, "check_sensor_alert", return_value=None):
            result = uc.handle_sensor_data("pir", "CLEAR")

        assert result is True
        # Production: is_on = (value_str.upper() == "DETECTED") if numeric_value is None else True
        # For "CLEAR" with numeric_value=None: is_on = ("CLEAR" == "DETECTED") = False
        assert status.is_on is False

    def test_ai_usecase_called_when_present(self, app_ctx):
        uc = _make_usecase(ai_usecase=MagicMock())
        device = MagicMock(); device.is_deleted = False; device.id = 3; device.code = "light"
        status = MagicMock()
        uc.device_repo.get_all_by_code.return_value = [device]
        uc.status_repo.get_or_create.return_value = status

        with patch.object(uc, "check_sensor_alert", return_value=None):
            uc.handle_sensor_data("light", 500)

        uc.ai_usecase.process_sensors.assert_called_once()

    def test_exception_returns_false(self, app_ctx):
        uc = _make_usecase()
        uc.device_repo.get_all_by_code.side_effect = Exception("DB error")
        result = uc.handle_sensor_data("sensor", 10)
        assert result is False


# ---------------------------------------------------------------------------
# check_sensor_alert
# ---------------------------------------------------------------------------

class TestCheckSensorAlert:
    def test_returns_none_when_no_rule(self, app_ctx):
        uc = _make_usecase()
        with patch("app.usecases.sensor_usecase.AlertRuleModel") as MockRule:
            MockRule.query.filter_by.return_value.first.return_value = None
            result = uc.check_sensor_alert(device_id=1, device_code="temp", current_value=30)
        assert result is None

    def test_max_value_exceeded_creates_alert(self, app_ctx):
        uc = _make_usecase()
        rule = MagicMock(); rule.max_value = 25; rule.min_value = None; rule.user_id = 1
        with patch("app.usecases.sensor_usecase.AlertRuleModel") as MockRule:
            MockRule.query.filter_by.return_value.first.return_value = rule
            result = uc.check_sensor_alert(device_id=1, device_code="temp", current_value=30)
        assert result is not None
        assert "exceeded max" in result
        uc.alert_repo.create.assert_called_once()

    def test_below_min_creates_alert(self, app_ctx):
        uc = _make_usecase()
        rule = MagicMock(); rule.max_value = None; rule.min_value = 10; rule.user_id = 1
        with patch("app.usecases.sensor_usecase.AlertRuleModel") as MockRule:
            MockRule.query.filter_by.return_value.first.return_value = rule
            result = uc.check_sensor_alert(device_id=1, device_code="temp", current_value=5)
        assert result is not None
        assert "below min" in result

    def test_normal_range_no_alert(self, app_ctx):
        uc = _make_usecase()
        rule = MagicMock(); rule.max_value = 30; rule.min_value = 10; rule.user_id = 1
        with patch("app.usecases.sensor_usecase.AlertRuleModel") as MockRule:
            MockRule.query.filter_by.return_value.first.return_value = rule
            result = uc.check_sensor_alert(device_id=1, device_code="temp", current_value=20)
        assert result is None
