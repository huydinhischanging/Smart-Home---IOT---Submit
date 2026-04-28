"""Unit tests for MedicineReminderUseCase — create, list, delete, dispatch."""
from datetime import date, datetime
from unittest.mock import MagicMock, patch
import pytest

from flask import Flask

from app.extensions.database import db
from app.infrastructure.persistence.models.medicine_reminder_model import MedicineReminderModel
from app.infrastructure.persistence.models.user_model import UserModel
from app.usecases.medicine_reminder_usecase import MedicineReminderUseCase


# ──────────────────────────────────────────────
# App fixture
# ──────────────────────────────────────────────

@pytest.fixture()
def app():
    a = Flask(__name__)
    a.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    db.init_app(a)
    with a.app_context():
        db.create_all()
        yield a
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def usecase(app):
    email = MagicMock()
    email.resolve_recipients.return_value = ["test@example.com"]
    email.send_message.return_value = {"sent": True, "recipients": ["test@example.com"]}

    alert_uc = MagicMock()
    return MedicineReminderUseCase(email_notifier=email, alert_usecase=alert_uc)


def _make_user(app):
    with app.app_context():
        from werkzeug.security import generate_password_hash
        u = UserModel(
            username="testuser",
            email="test@example.com",
            password=generate_password_hash("password123"),
            is_active=True,
        )
        db.session.add(u)
        db.session.commit()
        return u.id


# ──────────────────────────────────────────────
# Validation tests (no DB needed)
# ──────────────────────────────────────────────

def test_create_empty_name_raises(usecase, app):
    with app.app_context():
        with pytest.raises(ValueError, match="Medicine name is required"):
            usecase.create_for_user(
                user_id=1, name="", dose="1 tab", time_of_day="08:00", recurrence="daily", notify_email=None
            )


def test_create_name_too_long_raises(usecase, app):
    with app.app_context():
        with pytest.raises(ValueError, match="60 characters"):
            usecase.create_for_user(
                user_id=1, name="A" * 61, dose="1 tab", time_of_day="08:00", recurrence="daily", notify_email=None
            )


def test_create_invalid_time_raises(usecase, app):
    with app.app_context():
        with pytest.raises(ValueError, match="HH:MM"):
            usecase.create_for_user(
                user_id=1, name="Aspirin", dose="1 tab", time_of_day="8:00", recurrence="daily", notify_email=None
            )


def test_create_invalid_recurrence_raises(usecase, app):
    with app.app_context():
        with pytest.raises(ValueError, match="daily|weekday|weekend"):
            usecase.create_for_user(
                user_id=1, name="Aspirin", dose="1 tab", time_of_day="08:00", recurrence="monthly", notify_email=None
            )


# ──────────────────────────────────────────────
# DB-backed CRUD tests
# ──────────────────────────────────────────────

def test_create_and_list(usecase, app):
    with app.app_context():
        user_id = _make_user(app)
        reminder = usecase.create_for_user(
            user_id=user_id, name="Aspirin", dose="1 tablet",
            time_of_day="08:00", recurrence="daily", notify_email=None
        )
        db.session.commit()

        items = usecase.list_for_user(user_id)
        assert len(items) == 1
        assert items[0]["name"] == "Aspirin"
        assert items[0]["time"] == "08:00"
        assert items[0]["days"] == "daily"


def test_create_default_dose(usecase, app):
    with app.app_context():
        user_id = _make_user(app)
        reminder = usecase.create_for_user(
            user_id=user_id, name="Vitamin C", dose="",
            time_of_day="09:00", recurrence="weekday", notify_email=None
        )
        db.session.commit()
        assert reminder.dosage == "1 dose"


def test_delete_reminder(usecase, app):
    with app.app_context():
        user_id = _make_user(app)
        reminder = usecase.create_for_user(
            user_id=user_id, name="Metformin", dose="500mg",
            time_of_day="07:00", recurrence="daily", notify_email=None
        )
        db.session.commit()
        rid = reminder.id

        ok = usecase.delete(rid, user_id)
        assert ok is True
        assert MedicineReminderModel.query.get(rid) is None


def test_delete_wrong_user(usecase, app):
    with app.app_context():
        user_id = _make_user(app)
        reminder = usecase.create_for_user(
            user_id=user_id, name="Vitamin D", dose="1000IU",
            time_of_day="12:00", recurrence="daily", notify_email=None
        )
        db.session.commit()

        ok = usecase.delete(reminder.id, user_id=9999)
        assert ok is False


def test_list_empty(usecase, app):
    with app.app_context():
        user_id = _make_user(app)
        assert usecase.list_for_user(user_id) == []


# ──────────────────────────────────────────────
# dispatch_due_reminders
# ──────────────────────────────────────────────

def test_dispatch_sends_reminder(usecase, app):
    with app.app_context():
        user_id = _make_user(app)
        reminder = usecase.create_for_user(
            user_id=user_id, name="Blood Pressure Med", dose="10mg",
            time_of_day="10:00", recurrence="daily", notify_email=None
        )
        db.session.commit()

        now = datetime(2026, 4, 17, 10, 0, 0)
        dispatched = usecase.dispatch_due_reminders(now=now)
        assert dispatched == 1
        usecase.email_notifier.send_message.assert_called_once()


def test_dispatch_skips_already_sent_today(usecase, app):
    with app.app_context():
        user_id = _make_user(app)
        reminder = usecase.create_for_user(
            user_id=user_id, name="Aspirin", dose="81mg",
            time_of_day="08:00", recurrence="daily", notify_email=None
        )
        reminder.last_sent_on = date(2026, 4, 17)
        db.session.commit()

        now = datetime(2026, 4, 17, 8, 0, 0)
        dispatched = usecase.dispatch_due_reminders(now=now)
        assert dispatched == 0


def test_dispatch_window_minus_one_minute(usecase, app):
    """Reminder at 10:00 should fire when cron runs at 09:59."""
    with app.app_context():
        user_id = _make_user(app)
        reminder = usecase.create_for_user(
            user_id=user_id, name="Aspirin", dose="81mg",
            time_of_day="10:00", recurrence="daily", notify_email=None
        )
        db.session.commit()

        now = datetime(2026, 4, 17, 9, 59, 55)
        dispatched = usecase.dispatch_due_reminders(now=now)
        assert dispatched == 1


def test_dispatch_window_plus_one_minute(usecase, app):
    """Reminder at 10:00 should fire when cron runs at 10:01."""
    with app.app_context():
        user_id = _make_user(app)
        reminder = usecase.create_for_user(
            user_id=user_id, name="Aspirin", dose="81mg",
            time_of_day="10:00", recurrence="daily", notify_email=None
        )
        db.session.commit()

        now = datetime(2026, 4, 17, 10, 1, 5)
        dispatched = usecase.dispatch_due_reminders(now=now)
        assert dispatched == 1


def test_dispatch_skips_weekend_on_weekday(usecase, app):
    with app.app_context():
        user_id = _make_user(app)
        reminder = usecase.create_for_user(
            user_id=user_id, name="Weekend Vitamin", dose="1 tab",
            time_of_day="09:00", recurrence="weekend", notify_email=None
        )
        db.session.commit()

        # Monday = weekday
        monday = datetime(2026, 4, 20, 9, 0, 0)
        dispatched = usecase.dispatch_due_reminders(now=monday)
        assert dispatched == 0


def test_dispatch_sends_on_weekend(usecase, app):
    with app.app_context():
        user_id = _make_user(app)
        reminder = usecase.create_for_user(
            user_id=user_id, name="Weekend Vitamin", dose="1 tab",
            time_of_day="09:00", recurrence="weekend", notify_email=None
        )
        db.session.commit()

        # Saturday
        saturday = datetime(2026, 4, 18, 9, 0, 0)
        dispatched = usecase.dispatch_due_reminders(now=saturday)
        assert dispatched == 1


def test_dispatch_no_due_reminders(usecase, app):
    with app.app_context():
        user_id = _make_user(app)
        usecase.create_for_user(
            user_id=user_id, name="Night Med", dose="1 tab",
            time_of_day="22:00", recurrence="daily", notify_email=None
        )
        db.session.commit()

        now = datetime(2026, 4, 17, 8, 0, 0)
        dispatched = usecase.dispatch_due_reminders(now=now)
        assert dispatched == 0
