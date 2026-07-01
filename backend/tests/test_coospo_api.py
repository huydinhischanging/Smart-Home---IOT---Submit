"""Tests for coospo_api — HR monitor REST endpoints."""
import time
from unittest.mock import MagicMock, patch
import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from app.extensions.database import db
from app.infrastructure.persistence.models.user_model import UserModel
from app.presentation.api.auth_api import _make_token
from app.presentation.api.coospo_api import (
    coospo_bp,
    update_state,
    get_state,
    on_heart_rate_received,
    add_hr_alert,
    _state,
)


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def coospo_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    db.init_app(app)
    app.register_blueprint(coospo_bp, url_prefix="/api")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(app, username="coospo_user"):
    with app.app_context():
        user = UserModel(
            username=username,
            email=f"{username}@test.com",
            password=generate_password_hash("pass"),
            role="user",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        token = _make_token(user)
        return user.id, token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Module-level helpers (no app context needed)
# ---------------------------------------------------------------------------

class TestCoospoHelpers:
    def test_get_state_returns_dict(self):
        state = get_state()
        assert isinstance(state, dict)
        assert "bpm" in state

    def test_update_state_modifies_values(self):
        original_bpm = get_state()["bpm"]
        update_state(bpm=75)
        assert get_state()["bpm"] == 75
        update_state(bpm=original_bpm)

    def test_on_heart_rate_received_updates_state(self):
        on_heart_rate_received(80, device_name="TestDevice", room_temp=25.0)
        state = get_state()
        assert state["bpm"] == 80
        assert state["device_name"] == "TestDevice"
        assert state["room_temp"] == 25.0
        assert state["connected"] is True

    def test_add_hr_alert_appends(self):
        import app.presentation.api.coospo_api as mod
        initial_len = len(mod._hr_alerts)
        add_hr_alert({"bpm": 150, "risk": "high"})
        assert len(mod._hr_alerts) == initial_len + 1

    def test_add_hr_alert_caps_at_max(self):
        import app.presentation.api.coospo_api as mod
        mod._hr_alerts.clear()
        for i in range(110):
            add_hr_alert({"bpm": i})
        assert len(mod._hr_alerts) <= 100


# ---------------------------------------------------------------------------
# GET /api/coospo/hr_alert
# ---------------------------------------------------------------------------

class TestHrAlert:
    def test_returns_state_and_alerts(self, coospo_app):
        _, token = _make_user(coospo_app)
        client = coospo_app.test_client()
        resp = client.get("/api/coospo/hr_alert", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "state" in data
        assert "hr_alerts" in data
        # process handle should be stripped from state
        assert "process" not in data["state"]

    def test_requires_auth(self, coospo_app):
        client = coospo_app.test_client()
        resp = client.get("/api/coospo/hr_alert")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/coospo/status
# ---------------------------------------------------------------------------

class TestCoospoStatus:
    def test_returns_connected_false_when_no_process(self, coospo_app):
        update_state(process=None, connected=False, bpm=0)
        _, token = _make_user(coospo_app, "status_user")
        client = coospo_app.test_client()
        resp = client.get("/api/coospo/status", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["connected"] is False

    def test_returns_stale_when_no_update(self, coospo_app):
        update_state(process=None, connected=True, last_update=0)
        _, token = _make_user(coospo_app, "status2_user")
        client = coospo_app.test_client()
        resp = client.get("/api/coospo/status", headers=_auth(token))
        data = resp.get_json()
        assert data["stale"] is True

    def test_returns_bpm_from_state(self, coospo_app):
        update_state(bpm=72, process=None)
        _, token = _make_user(coospo_app, "status3_user")
        client = coospo_app.test_client()
        resp = client.get("/api/coospo/status", headers=_auth(token))
        data = resp.get_json()
        assert data["bpm"] == 72


# ---------------------------------------------------------------------------
# POST /api/coospo/connect — process start
# ---------------------------------------------------------------------------

class TestCoospoConnect:
    def test_returns_already_running_if_process_alive(self, coospo_app):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # process running
        update_state(process=mock_proc, connected=True, device_name="MockDevice")

        _, token = _make_user(coospo_app, "connect_user")
        client = coospo_app.test_client()
        resp = client.post("/api/coospo/connect", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "Already" in data["message"] or data.get("device_name") == "MockDevice"

        update_state(process=None, connected=False)

    def test_returns_404_when_script_not_found(self, coospo_app):
        update_state(process=None, connected=False)
        _, token = _make_user(coospo_app, "connect2_user")
        client = coospo_app.test_client()
        with patch("os.path.exists", return_value=False):
            resp = client.post("/api/coospo/connect", headers=_auth(token))
        assert resp.status_code == 404

    def test_starts_process_when_script_found(self, coospo_app):
        update_state(process=None, connected=False)
        _, token = _make_user(coospo_app, "connect3_user")
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])

        with patch("os.path.exists", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            client = coospo_app.test_client()
            resp = client.post("/api/coospo/connect", headers=_auth(token))

        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        update_state(process=None, connected=False)


# ---------------------------------------------------------------------------
# POST /api/coospo/disconnect
# ---------------------------------------------------------------------------

class TestCoospoDisconnect:
    def test_disconnects_running_process(self, coospo_app):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        update_state(process=mock_proc, connected=True)

        _, token = _make_user(coospo_app, "disc_user")
        client = coospo_app.test_client()
        resp = client.post("/api/coospo/disconnect", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        mock_proc.terminate.assert_called_once()

    def test_disconnect_when_no_process(self, coospo_app):
        update_state(process=None, connected=False)
        _, token = _make_user(coospo_app, "disc2_user")
        client = coospo_app.test_client()
        resp = client.post("/api/coospo/disconnect", headers=_auth(token))
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/coospo/debug_alert — disabled by default
# ---------------------------------------------------------------------------

class TestDebugAlert:
    def test_returns_404_when_disabled(self, coospo_app):
        import app.presentation.api.coospo_api as mod
        original = mod._ENABLE_DEBUG_ALERT
        mod._ENABLE_DEBUG_ALERT = False

        _, token = _make_user(coospo_app, "debug_user")
        client = coospo_app.test_client()
        resp = client.post("/api/coospo/debug_alert", headers=_auth(token), json={"bpm": 150})
        assert resp.status_code == 404

        mod._ENABLE_DEBUG_ALERT = original
