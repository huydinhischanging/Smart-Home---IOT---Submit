"""Tests for Automation API — schedules and automation rules CRUD."""
import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from app.extensions.database import db
from app.extensions.limiter import limiter
from app.presentation.api.auth_api import auth_api
from app.presentation.api.automation_api import automation_api
from app.infrastructure.persistence.models.user_model import UserModel
from app.infrastructure.persistence.models.device_model import Device


# ──────────────────────────────────────────────
# App fixture
# ──────────────────────────────────────────────

@pytest.fixture()
def app():
    a = Flask(__name__)
    a.config.update(
        SECRET_KEY="automation-test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
        RATELIMIT_ENABLED=False,
    )
    db.init_app(a)
    limiter.init_app(a)
    a.register_blueprint(auth_api, url_prefix="/api/auth")
    a.register_blueprint(automation_api)

    with a.app_context():
        # Import all models so their tables are registered before create_all()
        from app.infrastructure.persistence.models.user_model import UserModel  # noqa: F401
        from app.infrastructure.persistence.models.rooms_model import RoomModel  # noqa: F401
        from app.infrastructure.persistence.models.schedule_model import ScheduleModel  # noqa: F401
        from app.infrastructure.persistence.models.automation_model import AutomationModel  # noqa: F401
        from app.infrastructure.persistence.models.device_status_model import DeviceStatus  # noqa: F401
        from app.infrastructure.persistence.models.control_log_model import ControlLog  # noqa: F401
        from app.infrastructure.persistence.models.sensor_data_model import SensorData  # noqa: F401
        from app.infrastructure.persistence.models.alert_model import AlertModel  # noqa: F401
        from app.infrastructure.persistence.models.alert_rule_model import AlertRuleModel  # noqa: F401
        db.create_all()

    return a


@pytest.fixture()
def client(app):
    return app.test_client()


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _register_and_token(client, username="tester", email="tester@example.com"):
    client.post("/api/auth/register", json={
        "username": username, "email": email, "password": "Password1"
    })
    r = client.post("/api/auth/login", json={"identity": email, "password": "Password1"})
    return r.get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_device(app, user_id, name="Sensor01", code="SENS01"):
    with app.app_context():
        d = Device(name=name, code=code, user_id=user_id, category="sensor", is_deleted=False)
        db.session.add(d)
        db.session.commit()
        return d.id


def _get_user_id(app, email):
    with app.app_context():
        u = UserModel.query.filter_by(email=email).first()
        return u.id if u else None


# ──────────────────────────────────────────────
# Schedule tests
# ──────────────────────────────────────────────

def test_list_schedules_empty(client):
    token = _register_and_token(client)
    r = client.get("/api/automation/schedules", headers=_auth(token))
    assert r.status_code == 200
    assert r.get_json()["data"] == []


def test_list_schedules_requires_auth(client):
    r = client.get("/api/automation/schedules")
    assert r.status_code == 401


def test_create_schedule(client, app):
    token = _register_and_token(client)
    uid = _get_user_id(app, "tester@example.com")
    dev_id = _make_device(app, uid, name="Light01", code="L01")

    r = client.post("/api/automation/schedules", json={
        "device_id": dev_id,
        "action": "ON",
        "cron_expr": "0 7 * * 1-5",
    }, headers=_auth(token))
    assert r.status_code == 201
    assert r.get_json()["success"] is True
    assert "id" in r.get_json()


def test_create_schedule_missing_fields(client):
    token = _register_and_token(client)
    r = client.post("/api/automation/schedules", json={"device_id": 1}, headers=_auth(token))
    assert r.status_code == 400


def test_create_schedule_invalid_cron(client, app):
    token = _register_and_token(client)
    uid = _get_user_id(app, "tester@example.com")
    dev_id = _make_device(app, uid, name="Fan02", code="F02")

    r = client.post("/api/automation/schedules", json={
        "device_id": dev_id,
        "action": "OFF",
        "cron_expr": "not-a-cron",
    }, headers=_auth(token))
    assert r.status_code == 400


def test_schedule_appears_in_list(client, app):
    token = _register_and_token(client)
    uid = _get_user_id(app, "tester@example.com")
    dev_id = _make_device(app, uid, name="Lamp03", code="LP03")

    client.post("/api/automation/schedules", json={
        "device_id": dev_id,
        "action": "ON",
        "cron_expr": "0 8 * * *",
    }, headers=_auth(token))

    r = client.get("/api/automation/schedules", headers=_auth(token))
    assert len(r.get_json()["data"]) == 1
    assert r.get_json()["data"][0]["cron_expr"] == "0 8 * * *"


def test_delete_schedule(client, app):
    token = _register_and_token(client)
    uid = _get_user_id(app, "tester@example.com")
    dev_id = _make_device(app, uid, name="AC04", code="AC04")

    r_create = client.post("/api/automation/schedules", json={
        "device_id": dev_id,
        "action": "OFF",
        "cron_expr": "0 22 * * *",
    }, headers=_auth(token))
    sid = r_create.get_json()["id"]

    r_del = client.delete(f"/api/automation/schedules/{sid}", headers=_auth(token))
    assert r_del.status_code == 200

    r_list = client.get("/api/automation/schedules", headers=_auth(token))
    assert r_list.get_json()["data"] == []


def test_delete_nonexistent_schedule(client):
    token = _register_and_token(client)
    r = client.delete("/api/automation/schedules/9999", headers=_auth(token))
    assert r.status_code == 404


def test_toggle_schedule(client, app):
    token = _register_and_token(client)
    uid = _get_user_id(app, "tester@example.com")
    dev_id = _make_device(app, uid, name="Heater05", code="HT05")

    r_create = client.post("/api/automation/schedules", json={
        "device_id": dev_id,
        "action": "ON",
        "cron_expr": "0 6 * * *",
    }, headers=_auth(token))
    sid = r_create.get_json()["id"]

    r_toggle = client.patch(f"/api/automation/schedules/{sid}",
                            json={"is_active": False}, headers=_auth(token))
    assert r_toggle.status_code == 200
    assert r_toggle.get_json()["is_active"] is False


def test_schedule_isolated_between_users(client, app):
    token_a = _register_and_token(client, "alice", "alice@example.com")
    uid_a = _get_user_id(app, "alice@example.com")
    dev_id = _make_device(app, uid_a, name="AliceDev", code="ALD1")

    client.post("/api/automation/schedules", json={
        "device_id": dev_id, "action": "ON", "cron_expr": "0 9 * * *",
    }, headers=_auth(token_a))

    token_b = _register_and_token(client, "bob", "bob@example.com")
    r = client.get("/api/automation/schedules", headers=_auth(token_b))
    assert r.get_json()["data"] == []


# ──────────────────────────────────────────────
# Automation rule tests
# ──────────────────────────────────────────────

def test_list_automations_empty(client, app):
    token = _register_and_token(client)
    r = client.get("/api/automation/automations", headers=_auth(token))
    assert r.status_code == 200
    assert r.get_json()["data"] == []


def test_create_automation(client, app):
    token = _register_and_token(client)
    uid = _get_user_id(app, "tester@example.com")
    trigger_id = _make_device(app, uid, name="TempSensor", code="TS01")
    action_id = _make_device(app, uid, name="ACUnit", code="AU01")

    r = client.post("/api/automation/automations", json={
        "name": "Turn on AC when hot",
        "trigger_device_id": trigger_id,
        "trigger_condition": "value > 30",
        "action_device_id": action_id,
        "action_payload": "ON",
    }, headers=_auth(token))
    assert r.status_code == 201
    assert r.get_json()["success"] is True


def test_create_automation_missing_fields(client):
    token = _register_and_token(client)
    r = client.post("/api/automation/automations",
                    json={"name": "incomplete"}, headers=_auth(token))
    assert r.status_code == 400


def test_automation_appears_in_list(client, app):
    token = _register_and_token(client)
    uid = _get_user_id(app, "tester@example.com")
    t_id = _make_device(app, uid, name="PirSensor", code="PIR1")
    a_id = _make_device(app, uid, name="Alarm", code="ALM1")

    client.post("/api/automation/automations", json={
        "name": "Intruder alarm",
        "trigger_device_id": t_id,
        "trigger_condition": "is_on == true",
        "action_device_id": a_id,
        "action_payload": "ON",
    }, headers=_auth(token))

    r = client.get("/api/automation/automations", headers=_auth(token))
    assert len(r.get_json()["data"]) == 1
    assert r.get_json()["data"][0]["name"] == "Intruder alarm"


def test_delete_automation(client, app):
    token = _register_and_token(client)
    uid = _get_user_id(app, "tester@example.com")
    t_id = _make_device(app, uid, name="LdrSensor", code="LDR1")
    a_id = _make_device(app, uid, name="NightLight", code="NL01")

    r_c = client.post("/api/automation/automations", json={
        "name": "Night light on",
        "trigger_device_id": t_id,
        "trigger_condition": "value < 20",
        "action_device_id": a_id,
        "action_payload": "ON",
    }, headers=_auth(token))
    aid = r_c.get_json()["id"]

    r_del = client.delete(f"/api/automation/automations/{aid}", headers=_auth(token))
    assert r_del.status_code == 200

    r_list = client.get("/api/automation/automations", headers=_auth(token))
    assert r_list.get_json()["data"] == []


def test_delete_nonexistent_automation(client):
    token = _register_and_token(client)
    r = client.delete("/api/automation/automations/9999", headers=_auth(token))
    assert r.status_code == 404


def test_toggle_automation(client, app):
    token = _register_and_token(client)
    uid = _get_user_id(app, "tester@example.com")
    t_id = _make_device(app, uid, name="MotionSensor", code="MS01")
    a_id = _make_device(app, uid, name="Bulb", code="BLB1")

    r_c = client.post("/api/automation/automations", json={
        "name": "Motion light",
        "trigger_device_id": t_id,
        "trigger_condition": "is_on == true",
        "action_device_id": a_id,
        "action_payload": "ON",
    }, headers=_auth(token))
    aid = r_c.get_json()["id"]

    r_toggle = client.patch(f"/api/automation/automations/{aid}",
                            json={"is_active": False}, headers=_auth(token))
    assert r_toggle.status_code == 200
    assert r_toggle.get_json()["is_active"] is False
