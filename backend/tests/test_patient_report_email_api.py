from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from app.extensions.database import db
from app.infrastructure.persistence.models.patient_profile_model import PatientProfileModel
from app.infrastructure.persistence.models.user_model import UserModel
from app.presentation.api.auth_api import _make_token
from app.presentation.api.patient_report_api import patient_report_api


class FakeEmailNotifier:
    def __init__(self, sent=True):
        self.sent = sent
        self.calls = []
        self.resolved = []

    def resolve_recipients(self, user_email=None, extra=None, include_default_recipients=False):
        recipients = [user_email]
        if isinstance(extra, list):
            recipients.extend(extra)
        elif extra:
            recipients.append(extra)
        recipients = [value for value in recipients if value]
        self.resolved.append((user_email, extra, include_default_recipients, recipients))
        return recipients

    def send_message(self, subject, body, recipients=None, attachments=None):
        payload = {
            "subject": subject,
            "body": body,
            "recipients": list(recipients or []),
            "attachments": list(attachments or []),
        }
        self.calls.append(payload)
        return {
            "sent": self.sent,
            "reason": "ok" if self.sent else "email-not-configured",
            "recipients": payload["recipients"],
            "provider": "smtp",
        }


@pytest.fixture()
def patient_report_app(monkeypatch):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    db.init_app(app)
    app.register_blueprint(patient_report_api, url_prefix="/api/patient")

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(app, consent_pdf_export=True):
    with app.app_context():
        user = UserModel(
            username="elder-user",
            email="elder@example.com",
            password=generate_password_hash("Password123"),
            role="user",
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(PatientProfileModel(user_id=user.id, patient_name="Bruce Wayne", consent_pdf_export=consent_pdf_export))
        db.session.commit()
        token = _make_token(user)
        return user, token


def test_email_patient_report_sends_pdf_attachment(patient_report_app, monkeypatch):
    notifier = FakeEmailNotifier(sent=True)
    monkeypatch.setattr(
        "app.presentation.api.patient_report_api.container",
        SimpleNamespace(email_notifier=lambda: notifier),
    )
    _, token = _make_user(patient_report_app, consent_pdf_export=True)
    client = patient_report_app.test_client()

    response = client.post(
        "/api/patient/report/email",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "caregiver@example.com"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["delivery"]["sent"] is True
    assert payload["filename"].endswith(".pdf")
    assert notifier.resolved == [
        ("elder@example.com", "caregiver@example.com", False, ["elder@example.com", "caregiver@example.com"])
    ]
    assert notifier.calls[0]["recipients"] == ["elder@example.com", "caregiver@example.com"]
    assert notifier.calls[0]["attachments"][0]["filename"] == payload["filename"]
    assert notifier.calls[0]["attachments"][0]["mimetype"] == "application/pdf"
    assert notifier.calls[0]["attachments"][0]["content"].startswith(b"%PDF")


def test_email_patient_report_defaults_to_notification_email(patient_report_app, monkeypatch):
    notifier = FakeEmailNotifier(sent=True)
    monkeypatch.setattr(
        "app.presentation.api.patient_report_api.container",
        SimpleNamespace(email_notifier=lambda: notifier),
    )
    _, token = _make_user(patient_report_app, consent_pdf_export=True)
    client = patient_report_app.test_client()

    response = client.post(
        "/api/patient/report/email",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert notifier.resolved == [
        ("elder@example.com", None, False, ["elder@example.com"])
    ]
    assert notifier.calls[0]["recipients"] == ["elder@example.com"]


def test_email_patient_report_requires_bearer_token(patient_report_app, monkeypatch):
    notifier = FakeEmailNotifier(sent=True)
    monkeypatch.setattr(
        "app.presentation.api.patient_report_api.container",
        SimpleNamespace(email_notifier=lambda: notifier),
    )
    client = patient_report_app.test_client()

    response = client.post("/api/patient/report/email", json={})

    assert response.status_code == 401
    assert response.get_json()["message"] == "Authentication required"
    assert notifier.calls == []


def test_email_patient_report_returns_400_when_no_recipients(patient_report_app, monkeypatch):
    notifier = FakeEmailNotifier(sent=False)

    def _send_message(*args, **kwargs):
        payload = {
            "subject": kwargs.get("subject"),
            "body": kwargs.get("body"),
            "recipients": list(kwargs.get("recipients") or []),
            "attachments": list(kwargs.get("attachments") or []),
        }
        notifier.calls.append(payload)
        return {
            "sent": False,
            "reason": "no-recipients",
            "recipients": payload["recipients"],
            "provider": "smtp",
        }

    notifier.send_message = _send_message
    monkeypatch.setattr(
        "app.presentation.api.patient_report_api.container",
        SimpleNamespace(email_notifier=lambda: notifier),
    )
    _, token = _make_user(patient_report_app, consent_pdf_export=True)
    client = patient_report_app.test_client()

    response = client.post(
        "/api/patient/report/email",
        headers={"Authorization": f"Bearer {token}"},
        json={"recipients": []},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["message"] == "Failed to send patient report email"
    assert payload["delivery"] == {"sent": False}


def test_email_patient_report_returns_503_when_email_not_configured(patient_report_app, monkeypatch):
    notifier = FakeEmailNotifier(sent=False)

    def _send_message(*args, **kwargs):
        payload = {
            "subject": kwargs.get("subject"),
            "body": kwargs.get("body"),
            "recipients": list(kwargs.get("recipients") or []),
            "attachments": list(kwargs.get("attachments") or []),
        }
        notifier.calls.append(payload)
        return {
            "sent": False,
            "reason": "email-not-configured",
            "recipients": payload["recipients"],
            "provider": "smtp",
        }

    notifier.send_message = _send_message
    monkeypatch.setattr(
        "app.presentation.api.patient_report_api.container",
        SimpleNamespace(email_notifier=lambda: notifier),
    )
    _, token = _make_user(patient_report_app, consent_pdf_export=True)
    client = patient_report_app.test_client()

    response = client.post(
        "/api/patient/report/email",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "caregiver@example.com"},
    )

    assert response.status_code == 503
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["message"] == "Failed to send patient report email"
    assert payload["delivery"] == {"sent": False}


def test_email_patient_report_honors_pdf_consent(patient_report_app, monkeypatch):
    notifier = FakeEmailNotifier(sent=True)
    monkeypatch.setattr(
        "app.presentation.api.patient_report_api.container",
        SimpleNamespace(email_notifier=lambda: notifier),
    )
    _, token = _make_user(patient_report_app, consent_pdf_export=False)
    client = patient_report_app.test_client()

    response = client.post(
        "/api/patient/report/email",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "caregiver@example.com"},
    )

    assert response.status_code == 403
    assert response.get_json()["message"] == "User disabled PDF export consent"
    assert notifier.calls == []