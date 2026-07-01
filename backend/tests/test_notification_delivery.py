from datetime import datetime

import pytest
from flask import Flask

from app.extensions.database import db
from app.gateways.email_notifier import EmailNotifier
from app.infrastructure.persistence.models.medicine_reminder_model import MedicineReminderModel
from app.infrastructure.persistence.models.user_model import UserModel
from app.usecases.medicine_reminder_usecase import MedicineReminderUseCase


class DummyAlertUseCase:
    def __init__(self):
        self.created = []

    def create_alert(self, **payload):
        self.created.append(payload)
        return payload


class DummyEmailNotifier:
    def __init__(self):
        self.sent = []
        self.resolved = []

    def resolve_recipients(self, user_email=None, extra=None, include_default_recipients=False):
        recipients = [email for email in [user_email, extra] if email]
        self.resolved.append((user_email, extra, include_default_recipients, recipients))
        return recipients

    def send_message(self, subject, body, recipients=None, attachments=None):
        payload = {
            "subject": subject,
            "body": body,
            "recipients": list(recipients or []),
            "attachments": list(attachments or []),
        }
        self.sent.append(payload)
        return {
            "sent": True,
            "reason": "ok",
            "recipients": payload["recipients"],
        }


@pytest.fixture()
def db_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_parse_recipients_normalizes_and_deduplicates():
    recipients = EmailNotifier._parse_recipients(
        "caregiver@example.com; CAREGIVER@example.com, invalid, elder@example.com"
    )

    assert recipients == ["caregiver@example.com", "elder@example.com"]


def test_resolve_recipients_only_includes_default_targets_when_requested(monkeypatch):
    monkeypatch.setenv("ALERT_RECIPIENTS", "ops@example.com,backup@example.com")

    notifier = EmailNotifier()

    assert notifier.resolve_recipients(user_email="elder@example.com") == ["elder@example.com"]
    assert notifier.resolve_recipients(
        user_email="elder@example.com",
        include_default_recipients=True,
    ) == ["elder@example.com", "ops@example.com", "backup@example.com"]


def test_send_message_reports_missing_smtp_configuration(monkeypatch):
    for key in [
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_APP_PASSWORD",
        "SMTP_FROM_EMAIL",
        "ALERT_RECIPIENTS",
    ]:
        monkeypatch.delenv(key, raising=False)

    notifier = EmailNotifier()
    result = notifier.send_message(
        subject="SOS",
        body="Emergency",
        recipients=["caregiver@example.com"],
    )

    assert result == {
        "sent": False,
        "reason": "email-not-configured",
        "recipients": ["caregiver@example.com"],
    }


def test_configuration_status_reports_missing_fields(monkeypatch):
    for key in [
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_APP_PASSWORD",
        "SMTP_FROM_EMAIL",
        "ALERT_RECIPIENTS",
    ]:
        monkeypatch.delenv(key, raising=False)

    notifier = EmailNotifier()
    status = notifier.configuration_status()

    assert status["enabled"] is False
    assert status["provider"] == "none"
    assert status["default_recipients"] == []
    assert status["smtp_missing"] == ["SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM_EMAIL"]
    assert status["brevo_missing"] == ["BREVO_API_KEY", "SMTP_FROM_EMAIL"]
    assert status["missing"] == [
        "BREVO_API_KEY",
        "SMTP_FROM_EMAIL",
        "SMTP_HOST",
        "SMTP_PASSWORD",
        "SMTP_USERNAME",
    ]


def test_send_message_uses_tls_smtp(monkeypatch):
    events = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            events.append(("connect", host, port, timeout))

        def __enter__(self):
            events.append(("enter",))
            return self

        def __exit__(self, exc_type, exc, tb):
            events.append(("exit",))

        def ehlo(self):
            events.append(("ehlo",))

        def starttls(self):
            events.append(("starttls",))

        def login(self, username, password):
            events.append(("login", username, password))

        def send_message(self, message):
            events.append(("send", message["Subject"], message["To"], message.get_content().strip()))

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "bot@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "alerts@example.com")
    monkeypatch.setenv("SMTP_FROM_NAME", "Batman Alerts")
    monkeypatch.setenv("SMTP_USE_TLS", "true")
    monkeypatch.setenv("SMTP_USE_SSL", "false")
    monkeypatch.setattr("app.gateways.email_notifier.smtplib.SMTP", FakeSMTP)

    notifier = EmailNotifier()
    result = notifier.send_message(
        subject="SOS Emergency",
        body="Alarm triggered",
        recipients=["caregiver@example.com"],
    )

    assert result == {
        "sent": True,
        "reason": "ok",
        "provider": "smtp",
        "recipients": ["caregiver@example.com"],
    }
    assert ("connect", "smtp.example.com", 587, 20) in events
    assert ("starttls",) in events
    assert ("login", "bot@example.com", "secret") in events
    assert (
        "send",
        "SOS Emergency",
        "caregiver@example.com",
        "Alarm triggered",
    ) in events


def test_send_message_accepts_smtp_app_password_alias(monkeypatch):
    events = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            pass

        def starttls(self):
            pass

        def login(self, username, password):
            events.append(("login", username, password))

        def send_message(self, message):
            events.append(("send", message["To"]))

    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "bot@example.com")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setenv("SMTP_APP_PASSWORD", "gmail-app-password")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "alerts@example.com")
    monkeypatch.setattr("app.gateways.email_notifier.smtplib.SMTP", FakeSMTP)

    notifier = EmailNotifier()
    result = notifier.send_message(
        subject="Alias test",
        body="Body",
        recipients=["caregiver@example.com"],
    )

    assert result["sent"] is True
    assert ("login", "bot@example.com", "gmail-app-password") in events


def test_send_message_includes_smtp_attachments(monkeypatch):
    events = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            pass

        def starttls(self):
            pass

        def login(self, username, password):
            pass

        def send_message(self, message):
            attachments = []
            for part in message.iter_attachments():
                attachments.append((part.get_filename(), part.get_content_type(), part.get_payload(decode=True)))
            events.append(attachments)

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "bot@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "alerts@example.com")
    monkeypatch.setattr("app.gateways.email_notifier.smtplib.SMTP", FakeSMTP)

    notifier = EmailNotifier()
    result = notifier.send_message(
        subject="Patient Report",
        body="Attached report",
        recipients=["caregiver@example.com"],
        attachments=[
            {
                "filename": "report.pdf",
                "content": b"pdf-bytes",
                "mimetype": "application/pdf",
            }
        ],
    )

    assert result["sent"] is True
    assert events == [[("report.pdf", "application/pdf", b"pdf-bytes")]]


def test_send_message_uses_brevo_when_smtp_is_not_configured(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 201
        text = '{"messageId":"abc123"}'

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    for key in ["SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SMTP_FROM_EMAIL", "alerts@example.com")
    monkeypatch.setenv("SMTP_FROM_NAME", "Batman Alerts")
    monkeypatch.setenv("BREVO_API_KEY", "brevo-secret")
    monkeypatch.setattr("app.gateways.email_notifier.requests.post", fake_post)

    notifier = EmailNotifier()
    result = notifier.send_message(
        subject="Medicine Reminder",
        body="Take your medicine",
        recipients=["caregiver@example.com"],
    )

    assert result == {
        "sent": True,
        "reason": "ok",
        "provider": "brevo",
        "recipients": ["caregiver@example.com"],
    }
    assert captured["url"] == "https://api.brevo.com/v3/smtp/email"
    assert captured["headers"]["api-key"] == "brevo-secret"
    assert captured["json"]["sender"] == {
        "email": "alerts@example.com",
        "name": "Batman Alerts",
    }
    assert captured["json"]["to"] == [{"email": "caregiver@example.com"}]
    assert captured["json"]["subject"] == "Medicine Reminder"


def test_send_message_includes_brevo_attachments(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 201
        text = '{"messageId":"abc123"}'

    def fake_post(url, json, headers, timeout):
        captured["json"] = json
        return FakeResponse()

    for key in ["SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SMTP_FROM_EMAIL", "alerts@example.com")
    monkeypatch.setenv("BREVO_API_KEY", "brevo-secret")
    monkeypatch.setattr("app.gateways.email_notifier.requests.post", fake_post)

    notifier = EmailNotifier()
    result = notifier.send_message(
        subject="Patient Report",
        body="Attached report",
        recipients=["caregiver@example.com"],
        attachments=[{"filename": "report.pdf", "content": b"pdf-bytes", "mimetype": "application/pdf"}],
    )

    assert result["sent"] is True
    assert captured["json"]["attachment"] == [
        {"name": "report.pdf", "content": "cGRmLWJ5dGVz"}
    ]


def test_dispatch_due_reminders_sends_email_creates_alert_and_marks_sent(db_app):
    email_notifier = DummyEmailNotifier()
    alert_usecase = DummyAlertUseCase()
    usecase = MedicineReminderUseCase(email_notifier, alert_usecase)

    with db_app.app_context():
        user = UserModel(
            username="elder-user",
            email="elder@example.com",
            password="hashed",
        )
        db.session.add(user)
        db.session.commit()

        reminder = MedicineReminderModel(
            user_id=user.id,
            medicine_name="Aspirin",
            dosage="1 pill",
            time_of_day="08:30",
            recurrence="daily",
            notify_email="caregiver@example.com",
            is_active=True,
        )
        db.session.add(reminder)
        db.session.commit()

        dispatched = usecase.dispatch_due_reminders(now=datetime(2026, 4, 14, 8, 30))
        db.session.refresh(reminder)

    assert dispatched == 1
    assert email_notifier.resolved == [
        ("elder@example.com", "caregiver@example.com", False, ["elder@example.com", "caregiver@example.com"])
    ]
    assert email_notifier.sent[0]["subject"] == "Medicine Reminder: Aspirin"
    assert email_notifier.sent[0]["recipients"] == [
        "elder@example.com",
        "caregiver@example.com",
    ]
    assert reminder.last_sent_on.isoformat() == "2026-04-14"
    assert alert_usecase.created[0]["device_code"] == "MEDICINE"
    assert "Email sent to 2 recipient(s)." in alert_usecase.created[0]["message"]


def test_dispatch_due_reminders_defaults_to_registered_user_email(db_app):
    email_notifier = DummyEmailNotifier()
    alert_usecase = DummyAlertUseCase()
    usecase = MedicineReminderUseCase(email_notifier, alert_usecase)

    with db_app.app_context():
        user = UserModel(
            username="elder-default",
            email="elder-default@example.com",
            password="hashed",
        )
        db.session.add(user)
        db.session.commit()

        reminder = MedicineReminderModel(
            user_id=user.id,
            medicine_name="Omega 3",
            dosage="1 capsule",
            time_of_day="09:00",
            recurrence="daily",
            notify_email=None,
            is_active=True,
        )
        db.session.add(reminder)
        db.session.commit()

        dispatched = usecase.dispatch_due_reminders(now=datetime(2026, 4, 14, 9, 0))
        db.session.refresh(reminder)

    assert dispatched == 1
    assert email_notifier.resolved == [
        ("elder-default@example.com", None, False, ["elder-default@example.com"])
    ]
    assert email_notifier.sent[0]["recipients"] == ["elder-default@example.com"]
    assert reminder.last_sent_on.isoformat() == "2026-04-14"
    assert "Email sent to 1 recipient(s)." in alert_usecase.created[0]["message"]


def test_dispatch_due_reminders_skips_when_already_sent_today(db_app):
    email_notifier = DummyEmailNotifier()
    alert_usecase = DummyAlertUseCase()
    usecase = MedicineReminderUseCase(email_notifier, alert_usecase)

    with db_app.app_context():
        user = UserModel(
            username="elder-repeat",
            email="repeat@example.com",
            password="hashed",
        )
        db.session.add(user)
        db.session.commit()

        reminder = MedicineReminderModel(
            user_id=user.id,
            medicine_name="Vitamin D",
            dosage="2 tablets",
            time_of_day="08:30",
            recurrence="daily",
            notify_email=None,
            is_active=True,
            last_sent_on=datetime(2026, 4, 14).date(),
        )
        db.session.add(reminder)
        db.session.commit()

        dispatched = usecase.dispatch_due_reminders(now=datetime(2026, 4, 14, 8, 30))

    assert dispatched == 0
    assert email_notifier.sent == []
    assert alert_usecase.created == []