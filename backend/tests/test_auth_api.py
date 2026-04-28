from flask import Flask
from itsdangerous import SignatureExpired

from app.extensions.database import db
from app.extensions.limiter import limiter
from app.infrastructure.persistence.models.user_model import UserModel
from app.presentation.api import auth_api as auth_api_module
from app.presentation.api.auth_api import auth_api


def _make_auth_app():
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
    return app


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


class _FakeEmailNotifier:
    def __init__(self, *, sent=True):
        self.sent = sent
        self.messages = []

    def resolve_recipients(self, user_email=None, extra=None, include_default_recipients=False):
        recipients = []
        if user_email:
            recipients.append(user_email)
        if extra:
            recipients.append(extra)
        return recipients

    def send_message(self, subject, body, recipients=None, attachments=None, html_body=None):
        self.messages.append({
            "subject": subject,
            "body": body,
            "html_body": html_body,
            "recipients": recipients or [],
        })
        return {
            "sent": self.sent,
            "reason": "ok" if self.sent else "email-not-configured",
            "recipients": recipients or [],
        }


class _FakeContainer:
    def __init__(self, notifier):
        self._notifier = notifier

    def email_notifier(self):
        return self._notifier


def test_register_creates_user_and_lowercases_email():
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        response = client.post(
            "/api/auth/register",
            json={
                "username": "elder-user",
                "email": "Elder@Example.com",
                "password": "Password123",
            },
        )

        assert response.status_code == 201
        payload = response.get_json()
        assert payload["status"] == "success"
        assert payload["token"]
        assert payload["user"]["username"] == "elder-user"
        assert payload["user"]["email"] == "elder@example.com"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_register_rejects_duplicate_email():
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        first = client.post(
            "/api/auth/register",
            json={
                "username": "elder-user",
                "email": "elder@example.com",
                "password": "Password123",
            },
        )
        assert first.status_code == 201

        duplicate = client.post(
            "/api/auth/register",
            json={
                "username": "elder-user-2",
                "email": "elder@example.com",
                "password": "Password123",
            },
        )

        assert duplicate.status_code == 409
        assert duplicate.get_json()["message"] == "Email already exists"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_login_accepts_email_and_username():
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        register = client.post(
            "/api/auth/register",
            json={
                "username": "elder-user",
                "email": "elder@example.com",
                "password": "Password123",
            },
        )
        assert register.status_code == 201

        email_login = client.post(
            "/api/auth/login",
            json={"identity": "elder@example.com", "password": "Password123"},
        )
        username_login = client.post(
            "/api/auth/login",
            json={"identity": "elder-user", "password": "Password123"},
        )

        assert email_login.status_code == 200
        assert email_login.get_json()["status"] == "success"
        assert "batman_os_auth=" in email_login.headers.get("Set-Cookie", "")
        assert username_login.status_code == 200
        assert username_login.get_json()["status"] == "success"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_me_and_refresh_require_and_accept_bearer_token():
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()

        unauthorized_me = client.get("/api/auth/me")
        unauthorized_refresh = client.post("/api/auth/refresh")
        assert unauthorized_me.status_code == 401
        assert unauthorized_refresh.status_code == 401

        register = client.post(
            "/api/auth/register",
            json={
                "username": "elder-user",
                "email": "elder@example.com",
                "password": "Password123",
            },
        )
        token = register.get_json()["token"]

        me = client.get("/api/auth/me", headers=_bearer(token))
        refresh = client.post("/api/auth/refresh", headers=_bearer(token))

        assert me.status_code == 200
        me_payload = me.get_json()
        assert me_payload["status"] == "success"
        assert me_payload["user"]["email"] == "elder@example.com"

        assert refresh.status_code == 200
        refresh_payload = refresh.get_json()
        assert refresh_payload["status"] == "success"
        assert refresh_payload["token"]
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_me_accepts_http_only_auth_cookie_without_bearer_header():
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        login = client.post(
            "/api/auth/register",
            json={
                "username": "cookie-user",
                "email": "cookie@example.com",
                "password": "Password123",
            },
        )

        assert login.status_code == 201
        assert "batman_os_auth=" in login.headers.get("Set-Cookie", "")

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.get_json()["user"]["email"] == "cookie@example.com"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_refresh_rotates_http_only_auth_cookie():
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        register = client.post(
            "/api/auth/register",
            json={
                "username": "cookie-refresh-user",
                "email": "cookie-refresh@example.com",
                "password": "Password123",
            },
        )
        old_cookie = register.headers.get("Set-Cookie", "")

        refreshed = client.post("/api/auth/refresh")

        assert refreshed.status_code == 200
        new_cookie = refreshed.headers.get("Set-Cookie", "")
        assert "batman_os_auth=" in new_cookie
        assert new_cookie != old_cookie
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_logout_clears_auth_cookie_and_blocks_cookie_only_session():
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        register = client.post(
            "/api/auth/register",
            json={
                "username": "logout-user",
                "email": "logout@example.com",
                "password": "Password123",
            },
        )
        assert register.status_code == 201

        before_logout = client.get("/api/auth/me")
        assert before_logout.status_code == 200

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200
        assert "batman_os_auth=;" in logout.headers.get("Set-Cookie", "")

        after_logout = client.get("/api/auth/me")
        assert after_logout.status_code == 401
        assert after_logout.get_json()["message"] == "Authentication required"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_me_rejects_invalid_bearer_token():
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        response = client.get("/api/auth/me", headers=_bearer("not-a-valid-token"))

        assert response.status_code == 401
        assert response.get_json()["message"] == "Invalid token"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_me_rejects_expired_token(monkeypatch):
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        register = client.post(
            "/api/auth/register",
            json={
                "username": "elder-user",
                "email": "elder@example.com",
                "password": "Password123",
            },
        )
        token = register.get_json()["token"]

        monkeypatch.setattr(
            auth_api_module,
            "_decode_token",
            lambda incoming_token: (_ for _ in ()).throw(SignatureExpired("expired"))
            if incoming_token == token else None,
        )

        response = client.get("/api/auth/me", headers=_bearer(token))

        assert response.status_code == 401
        assert response.get_json()["message"] == "Token expired"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_me_rejects_inactive_user_even_with_valid_token():
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        register = client.post(
            "/api/auth/register",
            json={
                "username": "elder-user",
                "email": "elder@example.com",
                "password": "Password123",
            },
        )
        token = register.get_json()["token"]

        with app.app_context():
            user = UserModel.query.filter_by(email="elder@example.com").first()
            user.is_active = False
            db.session.commit()

        response = client.get("/api/auth/me", headers=_bearer(token))

        assert response.status_code == 401
        assert response.get_json()["message"] == "User not found or inactive"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_profile_update_changes_username_with_password_confirmation():
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        register = client.post(
            "/api/auth/register",
            json={
                "username": "elder-user",
                "email": "elder@example.com",
                "password": "Password123",
            },
        )
        token = register.get_json()["token"]

        response = client.patch(
            "/api/auth/profile",
            headers=_bearer(token),
            json={
                "new_username": "new-elder-user",
                "current_password": "Password123",
            },
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["status"] == "success"
        assert payload["user"]["username"] == "new-elder-user"

        me = client.get("/api/auth/me", headers=_bearer(token))
        assert me.status_code == 200
        assert me.get_json()["user"]["username"] == "new-elder-user"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_forgot_password_returns_reset_token_when_email_unavailable(monkeypatch):
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    notifier = _FakeEmailNotifier(sent=False)
    monkeypatch.setattr(auth_api_module, "container", _FakeContainer(notifier))

    try:
        client = app.test_client()
        register = client.post(
            "/api/auth/register",
            json={
                "username": "elder-user",
                "email": "elder@example.com",
                "password": "Password123",
            },
        )
        assert register.status_code == 201

        forgot = client.post(
            "/api/auth/forgot-password",
            json={"email": "elder@example.com"},
        )

        assert forgot.status_code == 200
        payload = forgot.get_json()
        assert payload["status"] == "success"
        assert payload["reset_token"]
        assert notifier.messages[0]["recipients"] == ["elder@example.com"]
        assert notifier.messages[0]["html_body"]
        assert payload["reset_token"] in notifier.messages[0]["html_body"]
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_reset_password_accepts_valid_reset_token(monkeypatch):
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    notifier = _FakeEmailNotifier(sent=False)
    monkeypatch.setattr(auth_api_module, "container", _FakeContainer(notifier))

    try:
        client = app.test_client()
        register = client.post(
            "/api/auth/register",
            json={
                "username": "elder-user",
                "email": "elder@example.com",
                "password": "Password123",
            },
        )
        assert register.status_code == 201

        forgot = client.post(
            "/api/auth/forgot-password",
            json={"email": "elder@example.com"},
        )
        reset_token = forgot.get_json()["reset_token"]

        reset = client.post(
            "/api/auth/reset-password",
            json={
                "token": reset_token,
                "new_password": "NewPassword456",
            },
        )
        assert reset.status_code == 200
        assert reset.get_json()["message"] == "Password reset successfully"

        login = client.post(
            "/api/auth/login",
            json={"identity": "elder@example.com", "password": "NewPassword456"},
        )
        assert login.status_code == 200
        assert login.get_json()["status"] == "success"

        reused = client.post(
            "/api/auth/reset-password",
            json={
                "token": reset_token,
                "new_password": "AnotherPassword789",
            },
        )
        assert reused.status_code == 401
        assert reused.get_json()["message"] == "Invalid reset token"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_reset_password_accepts_token_pasted_with_whitespace(monkeypatch):
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    notifier = _FakeEmailNotifier(sent=False)
    monkeypatch.setattr(auth_api_module, "container", _FakeContainer(notifier))

    try:
        client = app.test_client()
        register = client.post(
            "/api/auth/register",
            json={
                "username": "elder-user-2",
                "email": "elder2@example.com",
                "password": "Password123",
            },
        )
        assert register.status_code == 201

        forgot = client.post(
            "/api/auth/forgot-password",
            json={"email": "elder2@example.com"},
        )
        reset_token = forgot.get_json()["reset_token"]
        spaced_token = f"  {reset_token[:10]} \n {reset_token[10:]}  "

        reset = client.post(
            "/api/auth/reset-password",
            json={
                "token": spaced_token,
                "new_password": "NewPassword456",
            },
        )
        assert reset.status_code == 200
        assert reset.get_json()["message"] == "Password reset successfully"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_forgot_password_hides_reset_token_when_fallback_disabled(monkeypatch):
    app = _make_auth_app()
    app.config["TESTING"] = False
    app.config["ALLOW_PASSWORD_RESET_TOKEN_FALLBACK"] = False

    with app.app_context():
        db.create_all()

    notifier = _FakeEmailNotifier(sent=False)
    monkeypatch.setattr(auth_api_module, "container", _FakeContainer(notifier))

    try:
        client = app.test_client()
        register = client.post(
            "/api/auth/register",
            json={
                "username": "elder-user",
                "email": "elder@example.com",
                "password": "Password123",
            },
        )
        assert register.status_code == 201

        forgot = client.post(
            "/api/auth/forgot-password",
            json={"email": "elder@example.com"},
        )

        assert forgot.status_code == 200
        payload = forgot.get_json()
        assert payload["status"] == "success"
        assert "reset_token" not in payload
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_cancel_account_soft_deletes_user_and_blocks_login():
    app = _make_auth_app()

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        register = client.post(
            "/api/auth/register",
            json={
                "username": "elder-user",
                "email": "elder@example.com",
                "password": "Password123",
            },
        )
        token = register.get_json()["token"]

        response = client.delete(
            "/api/auth/account",
            headers=_bearer(token),
            json={"current_password": "Password123"},
        )

        assert response.status_code == 200
        assert response.get_json()["message"] == "Account cancelled successfully"

        me = client.get("/api/auth/me", headers=_bearer(token))
        assert me.status_code == 401
        assert me.get_json()["message"] == "User not found or inactive"

        login = client.post(
            "/api/auth/login",
            json={"identity": "elder@example.com", "password": "Password123"},
        )
        assert login.status_code == 401
        assert login.get_json()["message"] == "Invalid credentials"

        with app.app_context():
            deleted = UserModel.query.filter(UserModel.username.like("deleted-user-%")).first()
            assert deleted is not None
            assert deleted.is_active is False
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()