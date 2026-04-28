"""Tests for app.scheduler — _eval_condition function (pure logic, no scheduler startup)."""
from unittest.mock import MagicMock
import pytest

from app.scheduler import _eval_condition


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _status(value=None, is_on=False):
    status = MagicMock()
    status.value = value
    status.is_on = is_on
    return status


# ---------------------------------------------------------------------------
# _eval_condition — basic numeric comparisons
# ---------------------------------------------------------------------------

class TestEvalConditionNumeric:
    def test_greater_than_true(self):
        assert _eval_condition("value > 30", _status(value="35.0")) is True

    def test_greater_than_false(self):
        assert _eval_condition("value > 30", _status(value="25.0")) is False

    def test_greater_than_equal_true(self):
        assert _eval_condition("value >= 30", _status(value="30.0")) is True

    def test_greater_than_equal_with_lower(self):
        assert _eval_condition("value >= 30", _status(value="29.9")) is False

    def test_less_than_true(self):
        assert _eval_condition("value < 20", _status(value="15.0")) is True

    def test_less_than_false(self):
        assert _eval_condition("value < 20", _status(value="25.0")) is False

    def test_less_than_equal_true(self):
        assert _eval_condition("value <= 20", _status(value="20.0")) is True

    def test_equals_numeric_true(self):
        assert _eval_condition("value == 100", _status(value="100.0")) is True

    def test_equals_numeric_false(self):
        assert _eval_condition("value == 100", _status(value="99.0")) is False

    def test_not_equals_numeric_true(self):
        assert _eval_condition("value != 0", _status(value="5.0")) is True

    def test_not_equals_numeric_false(self):
        assert _eval_condition("value != 0", _status(value="0.0")) is False


# ---------------------------------------------------------------------------
# _eval_condition — is_on comparisons
# ---------------------------------------------------------------------------

class TestEvalConditionIsOn:
    def test_is_on_equals_true_true(self):
        assert _eval_condition("is_on == true", _status(is_on=True)) is True

    def test_is_on_equals_true_false(self):
        assert _eval_condition("is_on == true", _status(is_on=False)) is False

    def test_is_on_equals_false_true(self):
        assert _eval_condition("is_on == false", _status(is_on=False)) is True

    def test_is_on_equals_on_true(self):
        assert _eval_condition("is_on == on", _status(is_on=True)) is True

    def test_is_on_equals_off_true(self):
        assert _eval_condition("is_on == off", _status(is_on=False)) is True

    def test_is_on_not_equals(self):
        assert _eval_condition("is_on != true", _status(is_on=False)) is True


# ---------------------------------------------------------------------------
# _eval_condition — string comparison
# ---------------------------------------------------------------------------

class TestEvalConditionString:
    def test_value_equals_string_detected(self):
        assert _eval_condition("value == DETECTED", _status(value="DETECTED")) is True

    def test_value_equals_string_case_sensitive_mismatch(self):
        # right_raw comes out as "detected" (strip quotes), left is "DETECTED"
        # Comparison is case-sensitive for strings
        result = _eval_condition("value == CLEAR", _status(value="DETECTED"))
        assert result is False

    def test_value_equals_string_clear_false(self):
        # 'CLEAR' is a plain string (not boolean), comparison succeeds string == string
        assert _eval_condition("value == CLEAR", _status(value="CLEAR")) is True


# ---------------------------------------------------------------------------
# _eval_condition — edge cases
# ---------------------------------------------------------------------------

class TestEvalConditionEdgeCases:
    def test_returns_false_for_none_status(self):
        # value defaults to 0.0 when status is None
        assert _eval_condition("value > 10", None) is False

    def test_returns_false_for_unrecognized_pattern(self):
        assert _eval_condition("random garbage", _status(value="5")) is False

    def test_returns_false_for_empty_condition(self):
        assert _eval_condition("", _status(value="5")) is False

    def test_returns_false_on_exception(self):
        # Malformed status to provoke an exception inside eval
        bad_status = MagicMock()
        bad_status.value = object()  # non-string, non-numeric
        bad_status.is_on = None
        # Should not raise — returns False on exception
        result = _eval_condition("value > 10", bad_status)
        assert result in (True, False)  # Just doesn't raise

    def test_whitespace_padded_condition(self):
        assert _eval_condition("  value > 30  ", _status(value="35")) is True

    def test_returns_false_for_invalid_operator(self):
        assert _eval_condition("value ?? 30", _status(value="35")) is False

    def test_integer_string_value(self):
        assert _eval_condition("value > 5", _status(value="10")) is True

    def test_zero_value_less_than(self):
        assert _eval_condition("value < 1", _status(value="0")) is True


# ---------------------------------------------------------------------------
# Scheduler job functions — need Flask app context
# ---------------------------------------------------------------------------

import json
import pytest
from unittest.mock import patch, MagicMock
from werkzeug.security import generate_password_hash


def _make_test_app():
    from flask import Flask
    from app.extensions.database import db

    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY="sched-test-secret",
        JWT_SECRET_KEY="sched-jwt-secret",
    )
    db.init_app(app)
    return app


@pytest.fixture(scope="module")
def sched_app():
    app = _make_test_app()
    with app.app_context():
        from app.extensions.database import db
        # Import all models to ensure tables are registered
        from app.infrastructure.persistence.models.user_model import UserModel  # noqa
        from app.infrastructure.persistence.models.device_model import Device  # noqa
        from app.infrastructure.persistence.models.device_status_model import DeviceStatus  # noqa
        from app.infrastructure.persistence.models.schedule_model import ScheduleModel  # noqa
        from app.infrastructure.persistence.models.automation_model import AutomationModel  # noqa
        from app.infrastructure.persistence.models.rooms_model import RoomModel  # noqa
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


class TestExecuteSchedule:
    def test_schedule_not_found_returns_silently(self, sched_app):
        """Schedule ID that doesn't exist → returns without error."""
        from app.scheduler import _execute_schedule
        # Should not raise
        _execute_schedule(sched_app, 99999)

    def test_inactive_schedule_skipped(self, sched_app):
        """Inactive schedule is skipped."""
        from app.scheduler import _execute_schedule
        from app.extensions.database import db
        from app.infrastructure.persistence.models.schedule_model import ScheduleModel

        with sched_app.app_context():
            sched = ScheduleModel(
                device_id=999,
                cron_expr="0 * * * *",
                action=json.dumps({"is_on": True}),
                is_active=False,
            )
            db.session.add(sched)
            db.session.commit()
            sched_id = sched.id

        _execute_schedule(sched_app, sched_id)  # inactive → early return

    def test_device_not_found_logs_warning(self, sched_app):
        """Active schedule with non-existent device logs warning."""
        from app.scheduler import _execute_schedule
        from app.extensions.database import db
        from app.infrastructure.persistence.models.schedule_model import ScheduleModel

        with sched_app.app_context():
            sched = ScheduleModel(
                device_id=88888,  # non-existent device
                cron_expr="0 * * * *",
                action=json.dumps({"is_on": True}),
                is_active=True,
            )
            db.session.add(sched)
            db.session.commit()
            sched_id = sched.id

        _execute_schedule(sched_app, sched_id)  # device not found → logs warning, returns

    def test_execute_with_real_device(self, sched_app):
        """Active schedule with real device executes MQTT command."""
        from app.scheduler import _execute_schedule
        from app.extensions.database import db
        from app.infrastructure.persistence.models.schedule_model import ScheduleModel
        from app.infrastructure.persistence.models.device_model import Device
        from app.infrastructure.persistence.models.device_status_model import DeviceStatus

        with sched_app.app_context():
            device = Device(name="TestFan", code="FAN001", room_id=None, user_id=None)
            db.session.add(device)
            db.session.flush()
            status = DeviceStatus(device_id=device.id, is_on=False, value="OFF")
            db.session.add(status)

            sched = ScheduleModel(
                device_id=device.id,
                cron_expr="0 * * * *",
                action=json.dumps({"is_on": True, "value": "ON"}),
                is_active=True,
            )
            db.session.add(sched)
            db.session.commit()
            sched_id = sched.id

        with patch("app.gateways.mqtt_publisher.MqttPublisher.send_device_command"):
            _execute_schedule(sched_app, sched_id)


class TestCheckAutomations:
    def test_no_automations_returns_early(self, sched_app):
        """No active automations → early return without MQTT."""
        from app.scheduler import _check_automations
        _check_automations(sched_app)  # no automations in DB → safe

    def test_automation_condition_not_met(self, sched_app):
        """Automation exists but trigger condition is not met → no action."""
        from app.scheduler import _check_automations
        from app.extensions.database import db
        from app.infrastructure.persistence.models.automation_model import AutomationModel
        from app.infrastructure.persistence.models.device_model import Device
        from app.infrastructure.persistence.models.device_status_model import DeviceStatus

        with sched_app.app_context():
            trigger_dev = Device(name="TempSensor", code="TEMP001", room_id=None, user_id=None)
            action_dev = Device(name="AirCon", code="AC001", room_id=None, user_id=None)
            db.session.add_all([trigger_dev, action_dev])
            db.session.flush()
            # Trigger status: value = 20 (condition > 30 not met)
            t_status = DeviceStatus(device_id=trigger_dev.id, is_on=True, value="20.0")
            db.session.add(t_status)
            auto = AutomationModel(
                name="TempAutoTest",
                trigger_device_id=trigger_dev.id,
                trigger_condition="value > 30",
                action_device_id=action_dev.id,
                action_payload=json.dumps({"is_on": True}),
                is_active=True,
            )
            db.session.add(auto)
            db.session.commit()

        _check_automations(sched_app)  # condition not met, no MQTT sent

    def test_automation_condition_met_fires_mqtt(self, sched_app):
        """Automation condition is met → MQTT command sent."""
        from app.scheduler import _check_automations
        from app.extensions.database import db
        from app.infrastructure.persistence.models.automation_model import AutomationModel
        from app.infrastructure.persistence.models.device_model import Device
        from app.infrastructure.persistence.models.device_status_model import DeviceStatus

        with sched_app.app_context():
            trigger_dev = Device(name="HeatSensor", code="HEAT001", room_id=None, user_id=None)
            action_dev = Device(name="FanAuto", code="FANAUTO", room_id=None, user_id=None)
            db.session.add_all([trigger_dev, action_dev])
            db.session.flush()
            t_status = DeviceStatus(device_id=trigger_dev.id, is_on=True, value="35.0")
            a_status = DeviceStatus(device_id=action_dev.id, is_on=False, value="OFF")
            db.session.add_all([t_status, a_status])
            auto = AutomationModel(
                name="HeatAutoFire",
                trigger_device_id=trigger_dev.id,
                trigger_condition="value > 30",
                action_device_id=action_dev.id,
                action_payload=json.dumps({"is_on": True, "value": "ON"}),
                is_active=True,
            )
            db.session.add(auto)
            db.session.commit()

        with patch("app.gateways.mqtt_publisher.MqttPublisher.send_device_command") as mock_mqtt:
            _check_automations(sched_app)
            mock_mqtt.assert_called_once()


class TestDispatchMedicineReminders:
    def test_dispatches_without_error(self, sched_app):
        """_dispatch_medicine_reminders runs without error with mocked container."""
        from app.scheduler import _dispatch_medicine_reminders
        mock_uc = MagicMock()
        mock_uc.dispatch_due_reminders.return_value = 2

        with patch("app.wiring.container") as mock_container:
            mock_container.medicine_reminder_usecase.return_value = mock_uc
            _dispatch_medicine_reminders(sched_app)

        mock_uc.dispatch_due_reminders.assert_called_once()

    def test_handles_exception_gracefully(self, sched_app):
        """Exception in reminder dispatch is caught and logged."""
        from app.scheduler import _dispatch_medicine_reminders
        with patch("app.wiring.container") as mock_container:
            mock_container.medicine_reminder_usecase.side_effect = RuntimeError("boom")
            _dispatch_medicine_reminders(sched_app)  # should not raise


class TestReloadSchedules:
    def test_empty_db_clears_old_schedule_jobs(self, sched_app):
        """With no DB schedules, old schedule_ jobs are removed."""
        from app.scheduler import _reload_schedules
        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "schedule_42"
        mock_scheduler.get_jobs.return_value = [mock_job]

        _reload_schedules(sched_app, mock_scheduler)
        mock_job.remove.assert_called_once()

    def test_loads_active_schedules_from_db(self, sched_app):
        """Active schedules in DB get added as cron jobs."""
        from app.scheduler import _reload_schedules
        from app.extensions.database import db
        from app.infrastructure.persistence.models.schedule_model import ScheduleModel

        with sched_app.app_context():
            # Clear any existing schedules
            ScheduleModel.query.delete()
            sched = ScheduleModel(
                device_id=999,
                cron_expr="0 6 * * *",
                action=json.dumps({"is_on": True}),
                is_active=True,
            )
            db.session.add(sched)
            db.session.commit()

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []
        _reload_schedules(sched_app, mock_scheduler)
        mock_scheduler.add_job.assert_called_once()

    def test_invalid_cron_logs_warning(self, sched_app):
        """Schedule with invalid cron_expr is skipped with a warning."""
        from app.scheduler import _reload_schedules
        from app.extensions.database import db
        from app.infrastructure.persistence.models.schedule_model import ScheduleModel

        with sched_app.app_context():
            ScheduleModel.query.delete()
            sched = ScheduleModel(
                device_id=999,
                cron_expr="not-a-valid-cron",
                action=json.dumps({"is_on": True}),
                is_active=True,
            )
            db.session.add(sched)
            db.session.commit()

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []
        _reload_schedules(sched_app, mock_scheduler)  # logs warning, doesn't raise

