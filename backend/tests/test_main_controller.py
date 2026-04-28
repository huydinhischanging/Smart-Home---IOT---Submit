"""Tests for main_controller — /api/health and /api/metrics endpoints."""
import pytest
from flask import Flask

from app.extensions.database import db
from app.presentation.main.main_controller import main_controller


def _make_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
        MQTT_ENABLED=False,
    )
    db.init_app(app)
    app.register_blueprint(main_controller)
    with app.app_context():
        db.create_all()
    return app


# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------

class TestHealthcheck:
    def setup_method(self):
        self.app = _make_app()
        self.client = self.app.test_client()

    def test_health_returns_200_when_db_ok(self):
        resp = self.client.get("/api/health")
        assert resp.status_code == 200

    def test_health_status_ok(self):
        resp = self.client.get("/api/health")
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_health_service_name(self):
        resp = self.client.get("/api/health")
        data = resp.get_json()
        assert data["service"] == "alfred-backend"

    def test_health_version_present(self):
        resp = self.client.get("/api/health")
        data = resp.get_json()
        assert "version" in data

    def test_health_database_key(self):
        resp = self.client.get("/api/health")
        data = resp.get_json()
        assert "database" in data

    def test_health_database_status_ok(self):
        resp = self.client.get("/api/health")
        data = resp.get_json()
        assert data["database_status"] == "ok"

    def test_health_mqtt_enabled_field(self):
        resp = self.client.get("/api/health")
        data = resp.get_json()
        assert "mqtt_enabled" in data
        assert data["mqtt_enabled"] is False

    def test_health_uptime_seconds_present(self):
        resp = self.client.get("/api/health")
        data = resp.get_json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], int)
        assert data["uptime_seconds"] >= 0

    def test_health_environment_present(self):
        resp = self.client.get("/api/health")
        data = resp.get_json()
        assert "environment" in data

    def test_health_503_when_db_fails(self):
        from unittest.mock import patch, MagicMock
        app = _make_app()
        with app.app_context():
            with patch("app.extensions.database.db.session") as mock_sess:
                mock_sess.execute.side_effect = Exception("DB down")
                client = app.test_client()
                resp = client.get("/api/health")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["status"] == "degraded"


# ---------------------------------------------------------------------------
# /api/metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    def setup_method(self):
        self.app = _make_app()
        self.client = self.app.test_client()

    def test_metrics_returns_200(self):
        resp = self.client.get("/api/metrics")
        assert resp.status_code == 200

    def test_metrics_service_name(self):
        data = self.client.get("/api/metrics").get_json()
        assert data["service"] == "alfred-backend"

    def test_metrics_uptime_present(self):
        data = self.client.get("/api/metrics").get_json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], int)

    def test_metrics_uptime_human_present(self):
        data = self.client.get("/api/metrics").get_json()
        assert "uptime_human" in data
        assert isinstance(data["uptime_human"], str)

    def test_metrics_database_status_ok(self):
        data = self.client.get("/api/metrics").get_json()
        assert data["database_status"] == "ok"

    def test_metrics_environment_present(self):
        data = self.client.get("/api/metrics").get_json()
        assert "environment" in data

    def test_metrics_debug_mode_present(self):
        data = self.client.get("/api/metrics").get_json()
        assert "debug_mode" in data

    def test_metrics_mqtt_enabled_false(self):
        data = self.client.get("/api/metrics").get_json()
        assert data["mqtt_enabled"] is False


# ---------------------------------------------------------------------------
# _format_uptime helper
# ---------------------------------------------------------------------------

class TestFormatUptime:
    def test_seconds_only(self):
        from app.presentation.main.main_controller import _format_uptime
        result = _format_uptime(45)
        assert "45s" in result

    def test_minutes(self):
        from app.presentation.main.main_controller import _format_uptime
        result = _format_uptime(130)
        assert "2m" in result

    def test_hours(self):
        from app.presentation.main.main_controller import _format_uptime
        result = _format_uptime(3700)
        assert "1h" in result

    def test_days(self):
        from app.presentation.main.main_controller import _format_uptime
        result = _format_uptime(90000)
        assert "1d" in result
