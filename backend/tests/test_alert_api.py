import io
from datetime import datetime, timedelta, timezone

from flask import Flask

from app.extensions.database import db
from app.extensions.limiter import limiter
from app.infrastructure.persistence.models import AlertModel
from app.infrastructure.persistence.models.user_model import UserModel
from app.infrastructure.persistence.repositories.alert_repository import AlertRepository
from app.infrastructure.persistence.repositories.alert_saved_view_repository import AlertSavedViewRepository
from app.presentation.api import alert_api as alert_api_module
from app.presentation.api.alert_api import alert_api
from app.presentation.api.auth_api import auth_api
from app.usecases.alert_saved_view_usecase import AlertSavedViewUseCase
from app.usecases.alert_usecase import AlertUseCase


class _DummyRealtimeNotifier:
    def notify_alert(self, payload, user_id=None):
        return None


class _DummyEmailNotifier:
    def __init__(self):
        self.messages = []

    def resolve_recipients(self, user_email=None, extra=None, include_default_recipients=False):
        recipients = []
        if user_email:
            recipients.append(user_email)
        if include_default_recipients:
            recipients.extend(["caregiver@example.com", "doctor@example.com"])
        if extra:
            recipients.append(extra)
        return recipients

    def send_message(self, subject, body, recipients=None, attachments=None, html_body=None):
        self.messages.append({
            "subject": subject,
            "body": body,
            "recipients": recipients or [],
            "attachments": attachments or [],
            "html_body": html_body,
        })
        return {
            "sent": True,
            "reason": "ok",
            "provider": "smtp",
            "recipients": recipients or [],
        }

    def send_async(self, subject, body, recipients=None, attachments=None, html_body=None):
        """Synchronous in tests — no threading so assertions run immediately."""
        self.send_message(subject=subject, body=body, recipients=recipients,
                          attachments=attachments, html_body=html_body)


def _make_alert_app(monkeypatch):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
        RATELIMIT_ENABLED=False,
    )
    db.init_app(app)
    limiter.init_app(app)
    app.register_blueprint(auth_api, url_prefix="/api/auth")
    app.register_blueprint(alert_api, url_prefix="/api")

    usecase = AlertUseCase(AlertRepository(), _DummyRealtimeNotifier())
    saved_view_usecase = AlertSavedViewUseCase(AlertSavedViewRepository())
    email_notifier = _DummyEmailNotifier()
    monkeypatch.setattr(alert_api_module.container, "alert_usecase", lambda: usecase)
    monkeypatch.setattr(alert_api_module.container, "alert_saved_view_usecase", lambda: saved_view_usecase)
    monkeypatch.setattr(alert_api_module.container, "email_notifier", lambda: email_notifier)
    app.extensions["dummy_email_notifier"] = email_notifier
    return app


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, username, email):
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "Password123",
        },
    )
    assert response.status_code == 201
    return response.get_json()["token"]


def test_bulk_mark_read_marks_only_current_users_alerts(monkeypatch):
    app = _make_alert_app(monkeypatch)

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        user_token = _register(client, "elder-user", "elder@example.com")
        other_token = _register(client, "other-user", "other@example.com")

        with app.app_context():
            user_id = 1
            other_user_id = 2
            repo = AlertRepository()
            repo.create("HR", "Critical heart rate alert", "critical", user_id=user_id)
            repo.create("MED", "Medicine reminder warning", "warning", user_id=user_id)
            repo.create("OPS", "Other user's alert", "info", user_id=other_user_id)
            db.session.commit()

            alert_ids = [alert.id for alert in AlertModel.query.order_by(AlertModel.id.asc()).all()]

        response = client.patch(
            "/api/alerts/read",
            json={"ids": alert_ids},
            headers=_bearer(user_token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["marked"] == 2
        assert payload["unread"] == 0

        with app.app_context():
            user_alerts = AlertModel.query.filter_by(user_id=1).order_by(AlertModel.id.asc()).all()
            other_alert = AlertModel.query.filter_by(user_id=2).one()
            assert [alert.is_read for alert in user_alerts] == [True, True]
            assert other_alert.is_read is False

        other_view = client.get("/api/alerts", headers=_bearer(other_token))
        assert other_view.status_code == 200
        assert other_view.get_json()["unread"] == 1
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_bulk_mark_read_validates_payload(monkeypatch):
    app = _make_alert_app(monkeypatch)

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        token = _register(client, "elder-user", "elder@example.com")

        missing_list = client.patch(
            "/api/alerts/read",
            json={"ids": "not-a-list"},
            headers=_bearer(token),
        )
        assert missing_list.status_code == 400
        assert missing_list.get_json()["message"] == "ids must be a list of alert ids"

        empty_list = client.patch(
            "/api/alerts/read",
            json={"ids": []},
            headers=_bearer(token),
        )
        assert empty_list.status_code == 400
        assert empty_list.get_json()["message"] == "ids must contain at least one alert id"

        invalid_value = client.patch(
            "/api/alerts/read",
            json={"ids": [1, "oops"]},
            headers=_bearer(token),
        )
        assert invalid_value.status_code == 400
        assert invalid_value.get_json()["message"] == "ids must contain only integers"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_get_alerts_supports_backend_filters(monkeypatch):
    app = _make_alert_app(monkeypatch)

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        token = _register(client, "elder-user", "elder@example.com")
        _register(client, "other-user", "other@example.com")

        now = datetime.now(timezone.utc)
        with app.app_context():
            db.session.add_all([
                AlertModel(device_code="HR", message="Critical heart rate spike", level="critical", user_id=1, is_read=False, created_at=now),
                AlertModel(device_code="MED", message="Medicine reminder warning", level="warning", user_id=1, is_read=False, created_at=now - timedelta(days=2)),
                AlertModel(device_code="OPS", message="Routine system info", level="info", user_id=1, is_read=True, created_at=now - timedelta(days=40)),
                AlertModel(device_code="HR", message="Other user critical alert", level="critical", user_id=2, is_read=False, created_at=now),
            ])
            db.session.commit()

        response = client.get(
            "/api/alerts",
            query_string={
                "level": "critical",
                "unread": "true",
                "device_code": "HR",
                "q": "spike",
                "since": (now - timedelta(hours=1)).isoformat(),
            },
            headers=_bearer(token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["unread"] == 2
        assert payload["total"] == 1
        assert payload["summary"] == {"total": 1, "unread": 1, "critical": 1}
        assert len(payload["data"]) == 1
        assert payload["data"][0]["device_code"] == "HR"
        assert payload["data"][0]["level"] == "critical"
        assert "spike" in payload["data"][0]["message"].lower()
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_get_alerts_validates_filter_query_params(monkeypatch):
    app = _make_alert_app(monkeypatch)

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        token = _register(client, "elder-user", "elder@example.com")

        bad_level = client.get("/api/alerts?level=nope", headers=_bearer(token))
        assert bad_level.status_code == 400
        assert bad_level.get_json()["message"] == "level must be one of info, warning, critical"

        bad_unread = client.get("/api/alerts?unread=maybe", headers=_bearer(token))
        assert bad_unread.status_code == 400
        assert bad_unread.get_json()["message"] == "unread must be a boolean"

        bad_since = client.get("/api/alerts?since=not-a-date", headers=_bearer(token))
        assert bad_since.status_code == 400
        assert bad_since.get_json()["message"] == "since must be a valid ISO-8601 datetime"

        bad_sort = client.get("/api/alerts?sort=random", headers=_bearer(token))
        assert bad_sort.status_code == 400
        assert bad_sort.get_json()["message"] == "sort must be newest or oldest"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_get_alerts_supports_oldest_sort_and_total(monkeypatch):
    app = _make_alert_app(monkeypatch)

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        token = _register(client, "elder-user", "elder@example.com")

        now = datetime.now(timezone.utc)
        with app.app_context():
            db.session.add_all([
                AlertModel(device_code="A", message="Newest alert", level="info", user_id=1, is_read=False, created_at=now),
                AlertModel(device_code="B", message="Oldest alert", level="warning", user_id=1, is_read=False, created_at=now - timedelta(days=3)),
            ])
            db.session.commit()

        response = client.get(
            "/api/alerts",
            query_string={"sort": "oldest", "limit": 1, "offset": 0},
            headers=_bearer(token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["total"] == 2
        assert payload["summary"] == {"total": 2, "unread": 2, "critical": 0}
        assert len(payload["data"]) == 1
        assert payload["data"][0]["device_code"] == "B"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_trigger_sos_emails_signed_in_user_and_configured_recipients(monkeypatch):
    app = _make_alert_app(monkeypatch)

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        token = _register(client, "elder-user", "elder@example.com")

        response = client.post(
            "/api/alerts/sos",
            json={"note": "Need immediate help"},
            headers=_bearer(token),
        )

        assert response.status_code == 201
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["delivery"]["sent"] is True

        notifier = app.extensions["dummy_email_notifier"]
        assert notifier.messages[0]["recipients"] == [
            "elder@example.com",
            "caregiver@example.com",
            "doctor@example.com",
        ]
        assert "Need immediate help" in notifier.messages[0]["body"]
        assert notifier.messages[0]["html_body"]
        assert "SOS Emergency Alert" in notifier.messages[0]["html_body"]
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_trigger_sos_accepts_voice_note_attachment(monkeypatch):
    app = _make_alert_app(monkeypatch)

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        token = _register(client, "voice-user", "voice@example.com")

        response = client.post(
            "/api/alerts/sos",
            data={
                "note": "Audio evidence attached",
                "audio": (io.BytesIO(b"fake-webm-audio"), "sos-voice-note.webm", "audio/webm"),
            },
            headers=_bearer(token),
            content_type="multipart/form-data",
        )

        assert response.status_code == 201
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["audio_attached"] is True

        notifier = app.extensions["dummy_email_notifier"]
        assert len(notifier.messages[0]["attachments"]) == 1
        attachment = notifier.messages[0]["attachments"][0]
        assert attachment["filename"] == "sos-voice-note.webm"
        assert attachment["mimetype"] == "audio/webm"
        assert attachment["content"] == b"fake-webm-audio"
        assert "Voice note attached" in notifier.messages[0]["html_body"]
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_saved_views_api_is_user_scoped_and_normalized(monkeypatch):
    app = _make_alert_app(monkeypatch)

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        user_token = _register(client, "elder-user", "elder@example.com")
        other_token = _register(client, "other-user", "other@example.com")

        save_response = client.put(
            "/api/alerts/views",
            json={
                "views": [
                    {
                        "name": "Critical 24h",
                        "pinned": True,
                        "filter": "critical",
                        "timeRange": "24h",
                        "sort": "newest",
                    },
                    {
                        "name": "Critical 24h",
                        "pinned": False,
                        "filter": "warning",
                    },
                    {
                        "name": "Floor sensor",
                        "pinned": False,
                        "filter": "warning",
                        "deviceCode": "FLOOR-A",
                        "query": "wet floor",
                        "timeRange": "7d",
                        "sort": "oldest",
                    },
                ]
            },
            headers=_bearer(user_token),
        )

        assert save_response.status_code == 200
        payload = save_response.get_json()
        assert payload["success"] is True
        assert payload["data"] == [
            {
                "name": "Critical 24h",
                "kind": "saved",
                "pinned": True,
                "filter": "critical",
                "query": "",
                "deviceCode": "",
                "timeRange": "24h",
                "sort": "newest",
            },
            {
                "name": "Floor sensor",
                "kind": "saved",
                "pinned": False,
                "filter": "warning",
                "query": "wet floor",
                "deviceCode": "FLOOR-A",
                "timeRange": "7d",
                "sort": "oldest",
            },
        ]

        user_views = client.get("/api/alerts/views", headers=_bearer(user_token))
        assert user_views.status_code == 200
        assert user_views.get_json()["data"] == payload["data"]

        other_views = client.get("/api/alerts/views", headers=_bearer(other_token))
        assert other_views.status_code == 200
        assert other_views.get_json()["data"] == []
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_saved_views_api_validates_payload(monkeypatch):
    app = _make_alert_app(monkeypatch)

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        token = _register(client, "elder-user", "elder@example.com")

        response = client.put(
            "/api/alerts/views",
            json={"views": {"name": "not-a-list"}},
            headers=_bearer(token),
        )

        assert response.status_code == 400
        assert response.get_json()["message"] == "views must be a list"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_saved_views_stats_requires_admin(monkeypatch):
    app = _make_alert_app(monkeypatch)

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        token = _register(client, "elder-user", "elder@example.com")

        response = client.get("/api/alerts/views/stats", headers=_bearer(token))
        assert response.status_code == 403
        assert response.get_json()["message"] == "Admin access required"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_saved_views_stats_returns_admin_summary(monkeypatch):
    app = _make_alert_app(monkeypatch)

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        admin_token = _register(client, "admin-user", "admin@example.com")
        user_token = _register(client, "elder-user", "elder@example.com")

        with app.app_context():
            admin_user = db.session.get(UserModel, 1)
            admin_user.role = "admin"
            db.session.commit()

        admin_save = client.put(
            "/api/alerts/views",
            json={
                "views": [
                    {"name": "Critical", "pinned": True, "filter": "critical"},
                    {"name": "Warnings", "pinned": False, "filter": "warning"},
                ]
            },
            headers=_bearer(admin_token),
        )
        assert admin_save.status_code == 200

        user_save = client.put(
            "/api/alerts/views",
            json={
                "views": [
                    {"name": "Unread 24h", "pinned": True, "filter": "unread", "timeRange": "24h"},
                ]
            },
            headers=_bearer(user_token),
        )
        assert user_save.status_code == 200

        response = client.get("/api/alerts/views/stats?limit=5", headers=_bearer(admin_token))
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["data"]["total_configs"] == 2
        assert payload["data"]["total_saved_views"] == 3
        assert payload["data"]["total_pinned_views"] == 2
        assert len(payload["data"]["recent_users"]) == 2
        usernames = {row["username"] for row in payload["data"]["recent_users"]}
        assert usernames == {"admin-user", "elder-user"}
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()