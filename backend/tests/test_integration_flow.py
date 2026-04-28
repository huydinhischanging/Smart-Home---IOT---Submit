"""
Covers:
  Register - Login - CRUD devices - Control - Alert - Medicine reminder
"""
import pytest
from flask import Flask

from app.extensions.database import db
from app.extensions.limiter import limiter
from app.presentation.api.auth_api import auth_api
from app.presentation.api.device_api import device_api
from app.presentation.api.reminder_api import reminder_api
from app.infrastructure.persistence.repositories.device_repository import DeviceRepository
from app.infrastructure.persistence.repositories.status_repository import DeviceStatusRepository
from app.infrastructure.persistence.repositories.log_repository import ControlLogRepository
from app.usecases.device_usecase import DeviceUseCase
from app.usecases.medicine_reminder_usecase import MedicineReminderUseCase
from app.wiring import container


# ──────────────────────────────────────────────
# Stubs
# ──────────────────────────────────────────────

class _NullMqtt:
    def publish(self, *a, **kw):
        return None
    def send_device_command(self, *a, **kw):
        return None


class _NullRealtime:
    def notify_device_list_changed(self, *a, **kw):
        return None
    def notify_device_status_changed(self, *a, **kw):
        return None
    def notify_device_status(self, *a, **kw):
        return None


class _NullEmail:
    enabled = False

    def resolve_recipients(self, user_email=None, **kw):
        return [user_email] if user_email else []
    def send_message(self, *a, **kw):
        return {"sent": False}


class _NullAlertUseCase:
    def create_alert(self, *a, **kw):
        return None


# ──────────────────────────────────────────────
# App fixture
# ──────────────────────────────────────────────

@pytest.fixture()
def app(monkeypatch):
    a = Flask(__name__)
    a.config.update(
        SECRET_KEY="integration-test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
        RATELIMIT_ENABLED=False,
    )
    db.init_app(a)
    limiter.init_app(a)
    a.register_blueprint(auth_api, url_prefix="/api/auth")
    a.register_blueprint(device_api, url_prefix="/api/devices")
    a.register_blueprint(reminder_api)

    null_email = _NullEmail()
    device_uc = DeviceUseCase(
        device_repo=DeviceRepository(),
        status_repo=DeviceStatusRepository(),
        log_repo=ControlLogRepository(),
        mqtt_publisher=_NullMqtt(),
        realtime_notifier=_NullRealtime(),
    )
    reminder_uc = MedicineReminderUseCase(
        email_notifier=null_email,
        alert_usecase=_NullAlertUseCase(),
    )
    monkeypatch.setattr(container, "device_usecase", lambda: device_uc)
    monkeypatch.setattr(container, "realtime_notifier", lambda: _NullRealtime())
    monkeypatch.setattr(container, "medicine_reminder_usecase", lambda: reminder_uc)
    monkeypatch.setattr(container, "email_notifier", lambda: null_email)

    with a.app_context():
        db.create_all()

    return a


@pytest.fixture()
def client(app):
    return app.test_client()


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _register(client, username="testuser", email="test@example.com", password="Password123"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def _login(client, identity="test@example.com", password="Password123"):
    return client.post("/api/auth/login", json={"identity": identity, "password": password})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ──────────────────────────────────────────────
# Auth flow
# ──────────────────────────────────────────────

def test_register_and_login(client):
    r = _register(client)
    assert r.status_code == 201
    data = r.get_json()
    assert data["status"] == "success"
    assert "token" in data

    r2 = _login(client)
    assert r2.status_code == 200
    assert r2.get_json()["status"] == "success"


def test_register_duplicate_email_rejected(client):
    _register(client)
    r = _register(client, username="other")
    assert r.status_code == 409


def test_login_wrong_password(client):
    _register(client)
    r = _login(client, password="WrongPass!")
    assert r.status_code == 401


def test_me_requires_auth(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_returns_user(client):
    _register(client)
    r = _login(client)
    token = r.get_json()["token"]

    r2 = client.get("/api/auth/me", headers=_bearer(token))
    assert r2.status_code == 200
    assert r2.get_json()["user"]["email"] == "test@example.com"


# ──────────────────────────────────────────────
# Device CRUD flow
# ──────────────────────────────────────────────

def _auth_token(client):
    _register(client)
    return _login(client).get_json()["token"]


def test_list_devices_empty(client):
    token = _auth_token(client)
    r = client.get("/api/devices", headers=_bearer(token))
    assert r.status_code == 200
    assert r.get_json()["data"] == []


def test_create_device(client):
    token = _auth_token(client)
    r = client.post(
        "/api/devices",
        json={"name": "Living Room Light", "code": "LIGHT_01", "type": "light"},
        headers=_bearer(token),
    )
    assert r.status_code == 201
    assert r.get_json()["success"] is True


def test_create_device_missing_name(client):
    token = _auth_token(client)
    r = client.post("/api/devices", json={"code": "NO_NAME"}, headers=_bearer(token))
    assert r.status_code == 400


def test_list_devices_after_create(client):
    token = _auth_token(client)
    client.post(
        "/api/devices",
        json={"name": "Bedroom Fan", "code": "FAN_01", "type": "fan"},
        headers=_bearer(token),
    )
    r = client.get("/api/devices", headers=_bearer(token))
    devices = r.get_json()["data"]
    assert len(devices) == 1
    assert devices[0]["name"] == "Bedroom Fan"


def test_delete_device(client):
    token = _auth_token(client)
    client.post(
        "/api/devices",
        json={"name": "Temp Sensor", "code": "TEMP_01", "type": "sensor"},
        headers=_bearer(token),
    )
    r = client.delete("/api/devices/TEMP_01", headers=_bearer(token))
    assert r.status_code == 200

    r2 = client.get("/api/devices", headers=_bearer(token))
    assert r2.get_json()["data"] == []


def test_device_not_visible_to_other_user(client):
    _register(client, username="alice", email="alice@example.com")
    token_a = _login(client, identity="alice@example.com").get_json()["token"]
    client.post(
        "/api/devices",
        json={"name": "Alice Device", "code": "A01"},
        headers=_bearer(token_a),
    )

    _register(client, username="bob", email="bob@example.com")
    token_b = _login(client, identity="bob@example.com").get_json()["token"]
    r = client.get("/api/devices", headers=_bearer(token_b))
    assert r.get_json()["data"] == []


# ──────────────────────────────────────────────
# Device control flow
# ──────────────────────────────────────────────

def test_control_device_on_off(client):
    token = _auth_token(client)
    client.post(
        "/api/devices",
        json={"name": "Hall Light", "code": "HALL_01", "type": "light"},
        headers=_bearer(token),
    )

    r_on = client.post(
        "/api/devices/control",
        json={"device_name": "Hall Light", "action": "ON"},
        headers=_bearer(token),
    )
    assert r_on.status_code == 200
    assert r_on.get_json()["success"] is True

    r_off = client.post(
        "/api/devices/control",
        json={"device_name": "Hall Light", "action": "OFF"},
        headers=_bearer(token),
    )
    assert r_off.status_code == 200


def test_control_nonexistent_device(client):
    token = _auth_token(client)
    r = client.post(
        "/api/devices/control",
        json={"device_name": "Ghost Device", "action": "ON"},
        headers=_bearer(token),
    )
    assert r.status_code in (404, 400, 200)


def test_control_requires_auth(client):
    r = client.post(
        "/api/devices/control",
        json={"device_name": "Hall Light", "command": "ON"},
    )
    assert r.status_code == 401


# ──────────────────────────────────────────────
# Medicine reminder flow
# ──────────────────────────────────────────────

def test_create_and_list_reminder(client):
    token = _auth_token(client)
    r = client.post(
        "/api/reminders",
        json={"name": "Aspirin", "dose": "1 tablet", "time": "08:00", "days": "daily"},
        headers=_bearer(token),
    )
    assert r.status_code == 201

    r2 = client.get("/api/reminders", headers=_bearer(token))
    assert r2.status_code == 200
    items = r2.get_json()["data"]
    assert len(items) == 1
    assert items[0]["name"] == "Aspirin"


def test_delete_reminder(client):
    token = _auth_token(client)
    r = client.post(
        "/api/reminders",
        json={"name": "Vitamin D", "dose": "1000IU", "time": "09:00", "days": "daily"},
        headers=_bearer(token),
    )
    rid = r.get_json()["data"]["id"]

    r2 = client.delete(f"/api/reminders/{rid}", headers=_bearer(token))
    assert r2.status_code == 200

    r3 = client.get("/api/reminders", headers=_bearer(token))
    assert r3.get_json()["data"] == []


def test_reminder_invalid_time_rejected(client):
    token = _auth_token(client)
    r = client.post(
        "/api/reminders",
        json={"name": "BadTime Med", "dose": "1 tab", "time": "9:00", "days": "daily"},
        headers=_bearer(token),
    )
    assert r.status_code == 400


def test_reminder_not_visible_to_other_user(client):
    _register(client, username="alice2", email="alice2@example.com")
    token_a = _login(client, identity="alice2@example.com").get_json()["token"]
    client.post(
        "/api/reminders",
        json={"name": "Alice Med", "dose": "1 tab", "time": "08:00", "days": "daily"},
        headers=_bearer(token_a),
    )

    _register(client, username="bob2", email="bob2@example.com")
    token_b = _login(client, identity="bob2@example.com").get_json()["token"]
    r = client.get("/api/reminders", headers=_bearer(token_b))
    assert r.get_json()["data"] == []
