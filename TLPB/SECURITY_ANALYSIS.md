# SECURITY ANALYSIS - IoT Smart Home for Elderly

Author note: This document is written for non-security readers first, then mapped to real source code.

## 1) Security In One Page (for beginners)

Think of this system as a house:
- Authentication = front door key (token).
- Authorization = room permission (admin/user role).
- Rate limit = anti-spam gate (stop brute-force and flooding).
- CORS = who is allowed to call your API from browser.
- SQLAlchemy ORM = safe database query builder (avoid raw SQL injection mistakes).
- MQTT over TLS = encrypted IoT message transport.
- Security headers = browser hardening.

What this project already does well:
- Signed auth token with expiry.
- Password hashing (no plaintext password in DB).
- Role check (admin_required).
- Route-level throttling for login/register/reset.
- Password reset token is stored as SHA-256 hash, not raw token.
- CORS allowlist for API.
- Basic browser security headers + CSP + HSTS in non-debug mode.
- MQTT TLS config support in backend settings.

What is still a known gap (for honest defense answer):
- API is still HTTP in LAN demo mode unless deployed behind HTTPS reverse proxy.
- SECRET_KEY and INTERNAL_TOKEN can be ephemeral in development (good for dev convenience, not for production persistence).
- Socket.IO CORS can be too open if env is misconfigured.

---

## 2) Exact Security Mechanisms and Where They Are In Code

### 2.1 Authentication and token lifecycle

Main file:
- [backend/app/presentation/api/auth_api.py](../backend/app/presentation/api/auth_api.py)

Core points:
- Token generation with timestamp and nonce: `_make_token(...)`.
- Token verification with max age 7 days: `_decode_token(...)`.
- Token accepted from `Authorization: Bearer ...` or secure cookie.
- Global auth decorator: `auth_required`.
- Admin gate: `admin_required`.

Why this is secure enough for thesis scope:
- Signed token prevents tampering.
- Expiration limits replay window.
- Cookie is `HttpOnly` and `SameSite=Strict`.

### 2.2 Password security

Main file:
- [backend/app/presentation/api/auth_api.py](../backend/app/presentation/api/auth_api.py)

Core points:
- Register: `generate_password_hash(password)`.
- Login/profile/account delete checks: `check_password_hash(...)`.
- No plaintext storage.

### 2.3 Password reset security

Main files:
- [backend/app/presentation/api/auth_api.py](../backend/app/presentation/api/auth_api.py)
- [backend/app/infrastructure/persistence/models/password_reset_token_model.py](../backend/app/infrastructure/persistence/models/password_reset_token_model.py)

Core points:
- Raw reset token is generated with `secrets.token_urlsafe(24)`.
- DB stores only `sha256(token)` as `token_hash`.
- Token has expiry.
- One-time use (`used_at` marks consumed token).
- Creating a new token invalidates old pending tokens for that user.

### 2.4 Rate limiting / anti-bruteforce

Main file:
- [backend/app/extensions/limiter.py](../backend/app/extensions/limiter.py)

Usage examples:
- Register: `5/min; 20/hour`.
- Login: `10/min; 50/hour`.
- Reset password: `10/hour`.
- Many API routes in device/automation/coospo also use limiter.

### 2.5 CORS and browser hardening headers

Main file:
- [backend/app/__init__.py](../backend/app/__init__.py)

Core points:
- API CORS uses allowlist from `CORS_ORIGINS` env.
- Supports credentials for cookie auth flows.
- Security headers are injected in `@app.after_request`:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy`
  - `Permissions-Policy`
  - `Content-Security-Policy`
  - `Strict-Transport-Security` in non-debug mode.

### 2.6 Database safety (SQL injection prevention direction)

Main files:
- [backend/app/presentation/api/auth_api.py](../backend/app/presentation/api/auth_api.py)
- [backend/app/infrastructure/persistence/models/user_model.py](../backend/app/infrastructure/persistence/models/user_model.py)

Core points:
- Project uses SQLAlchemy ORM query API (`filter_by`, model query, session API).
- This avoids string-concatenated SQL style in application code.

Note for committee honesty:
- ORM does not magically remove all risk if raw SQL is used elsewhere, but this code path is ORM-based and follows safe query construction patterns.

### 2.7 MQTT transport security

Main files:
- [backend/app/config/settings.py](../backend/app/config/settings.py)
- [backend/app/extensions/mqtt.py](../backend/app/extensions/mqtt.py)

Core points:
- MQTT TLS options are loaded into app config (`MQTT_TLS_ENABLED`, CA cert, TLS version).
- MQTT extension uses non-blocking async connect and retry behavior.

Important clarification:
- `mqtt.py` focuses availability/reconnect behavior, while TLS policy comes from settings and broker config.

### 2.8 Secret and production safeguards

Main file:
- [backend/app/config/settings.py](../backend/app/config/settings.py)

Core points:
- Production requires non-placeholder `SECRET_KEY`, `INTERNAL_TOKEN`, and DB credentials.
- Development mode can auto-generate ephemeral secrets to avoid startup failure.

---

## 3) Security Data Flow (simple)

1. User login -> server verifies hash -> server signs token -> returns token + secure cookie.
2. Client calls protected API -> `auth_required` verifies token -> loads user -> route runs.
3. If attacker brute-forces login -> limiter throttles requests.
4. If browser from wrong origin calls API -> CORS blocks in browser layer.
5. If malicious payload attempts SQL injection style input in normal API paths -> ORM query methods reduce raw-SQL risk.
6. IoT messages to broker can be encrypted via MQTT TLS configuration.

---

## 4) Defense-ready speaking script (EN, 30-45s)

Our security model is layered. At identity level, we use signed bearer tokens with expiration and role checks. At credential level, passwords are hashed with Werkzeug and never stored in plaintext. At abuse-prevention level, sensitive routes like login and password reset are rate-limited using Flask-Limiter. At browser boundary, API access is controlled by CORS allowlists and security headers including CSP, X-Frame-Options, and HSTS in production mode. At data layer, the backend is ORM-driven with SQLAlchemy, reducing raw SQL injection risks. For IoT transport, MQTT supports TLS configuration through the backend settings. The main remaining production gap is enforcing HTTPS end-to-end in deployment.

---

## 5) Improvement checklist (practical next steps)

Priority 1 (must before production):
- Force HTTPS with reverse proxy (Nginx + Let's Encrypt).
- Set strict production secrets in environment only.
- Tighten Socket.IO CORS origins.

Priority 2:
- Add token revocation list / logout-all sessions.
- Add account lockout after repeated failed login.
- Add audit log for admin actions and auth events.

Priority 3:
- Add MQTT per-device ACL verification tests.
- Add automated security tests for auth/cors/headers/rate-limit.

---

## 6) Source Code Appendix (full for core security files)

### A) backend/app/extensions/limiter.py (full)

```python
import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Redis neu REDIS_URL duoc set, fallback memory cho dev
_storage_uri = os.environ.get("REDIS_URL", "memory://")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["500 per day", "100 per hour"],
    storage_uri=_storage_uri,
)
```

### B) backend/app/extensions/mqtt.py (full)

```python
import logging
from flask_mqtt import Mqtt

mqtt = Mqtt()
logger = logging.getLogger(__name__)

# paho MQTT_ERR_SUCCESS = 0 — returned so flask_mqtt doesn't complain
_MQTT_ERR_SUCCESS = 0


def init_mqtt(app):
    """
    Init Flask-MQTT with non-blocking connect so the app starts even when
    the EMQX broker is temporarily unavailable.

    flask_mqtt calls paho's synchronous client.connect() inside init_app(),
    which raises ConnectionRefusedError when the broker is down.
    We replace connect() with connect_async() before init_app so paho
    queues the connection internally and retries automatically via loop_start().
    """
    def _async_connect(host, port=1883, keepalive=60, **kwargs):
        try:
            mqtt.client.connect_async(host, port, keepalive=keepalive)
            mqtt.client.loop_start()
            logger.info("MQTT connecting async to %s:%s (auto-retry enabled)", host, port)
        except Exception as e:
            logger.warning("MQTT async connect failed: %s — will retry when broker is available", e)
        return _MQTT_ERR_SUCCESS  # flask_mqtt checks the return value

    original_connect = mqtt.client.connect
    mqtt.client.connect = _async_connect
    try:
        mqtt.init_app(app)
    finally:
        mqtt.client.connect = original_connect
```

### C) backend/app/infrastructure/persistence/models/password_reset_token_model.py (full)

```python
from datetime import datetime, timezone

from app.extensions.database import db


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PasswordResetTokenModel(db.Model):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        db.Index("idx_password_reset_token_user", "user_id"),
        db.Index("idx_password_reset_token_expiry", "expires_at"),
        db.Index("idx_password_reset_token_used", "used_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow_naive)

    def __repr__(self):
        return (
            f"<PasswordResetTokenModel id={self.id} user_id={self.user_id} "
            f"used={self.used_at is not None}>"
        )
```

### D) backend/app/__init__.py (security-relevant full section)

```python
# Security-relevant highlights from create_app()

_default_origins = (
    "http://127.0.0.1:5173,"
    "http://localhost:5173,"
    "https://127.0.0.1:5173,"
    "https://localhost:5173"
)
socketio.init_app(
    app,
    cors_allowed_origins=os.environ.get(
        "SOCKETIO_CORS_ORIGINS",
        _default_origins,
    ).split(","),
)

limiter.init_app(app)

_cors_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://127.0.0.1:5173,http://localhost:5173,https://127.0.0.1:5173,https://localhost:5173",
).split(",")
CORS(
    app,
    supports_credentials=True,
    resources={
        r"/api/*": {
            "origins": _cors_origins,
            "allow_headers": [
                "Content-Type",
                "X-INTERNAL-TOKEN",
                "Authorization",
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        }
    },
)

@socketio.on("connect")
def _on_socket_connect(auth=None):
    from app.presentation.api.auth_api import _decode_token

    try:
        token = auth.get("token") if isinstance(auth, dict) else None
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
        if not token:
            token = request.cookies.get("batman_os_auth", "").strip()
        if not token:
            return
        user_id = _decode_token(token)
        _sio_join_room(f"user_{user_id}")
    except Exception as exc:
        logger.debug("Socket.IO connect: token decode failed, no user room joined (%s)", exc)

@app.after_request
def _add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' wss: ws:; "
        "font-src 'self'; "
        "frame-ancestors 'none'"
    )
    if not app.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

### E) backend/app/presentation/api/auth_api.py (full security core)

```python
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import html
import secrets

from flask import Blueprint, current_app, jsonify, request, g, make_response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions.database import db
from app.extensions.limiter import limiter
from app.infrastructure.persistence.models.password_reset_token_model import PasswordResetTokenModel
from app.infrastructure.persistence.models.user_model import UserModel
from app.wiring import container


auth_api = Blueprint("auth_api", __name__)

_TOKEN_SALT = "iot-auth-token-v1"
_TOKEN_AGE_SEC = 60 * 60 * 24 * 7  # 7 days
_RESET_AGE_SEC = 60 * 30  # 30 minutes
_AUTH_COOKIE_NAME = "batman_os_auth"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def _make_token(user: UserModel) -> str:
    return _serializer().dumps(
        {
            "uid": user.id,
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "nonce": secrets.token_urlsafe(8),
        },
        salt=_TOKEN_SALT,
    )


def _decode_token(token: str) -> int:
    data = _serializer().loads(token, salt=_TOKEN_SALT, max_age=_TOKEN_AGE_SEC)
    return int(data["uid"])


def _auth_cookie_secure() -> bool:
    return bool(current_app.config.get("SESSION_COOKIE_SECURE", False))


def _clear_auth_cookie(response):
    response.delete_cookie(
        _AUTH_COOKIE_NAME,
        path='/',
        samesite='Lax',
    )
    return response


def _set_auth_cookie(response, token: str):
    response.set_cookie(
        _AUTH_COOKIE_NAME,
        token,
        max_age=_TOKEN_AGE_SEC,
        httponly=True,
        secure=_auth_cookie_secure(),
        samesite='Strict',
        path='/',
    )
    return response


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_reset_token(token: str) -> str:
    return "".join(str(token).split())


def _allow_reset_token_fallback() -> bool:
    return bool(
        current_app.config.get("TESTING")
        or current_app.config.get("ALLOW_PASSWORD_RESET_TOKEN_FALLBACK")
    )


def _issue_reset_token(user: UserModel) -> str:
    PasswordResetTokenModel.query.filter_by(user_id=user.id, used_at=None).delete()
    token = secrets.token_urlsafe(24)
    ttl_sec = int(current_app.config.get("PASSWORD_RESET_TOKEN_TTL_SEC", _RESET_AGE_SEC))
    db.session.add(
        PasswordResetTokenModel(
            user_id=user.id,
            token_hash=_hash_reset_token(token),
            expires_at=_utcnow_naive() + timedelta(seconds=ttl_sec),
        )
    )
    db.session.commit()
    return token


def _consume_reset_token(token: str) -> UserModel:
    token = _normalize_reset_token(token)
    record = PasswordResetTokenModel.query.filter_by(
        token_hash=_hash_reset_token(token)
    ).first()
    if not record or record.used_at is not None:
        raise BadSignature("Invalid reset token")

    now = _utcnow_naive()
    if record.expires_at <= now:
        db.session.delete(record)
        db.session.commit()
        raise SignatureExpired("Reset token expired")

    user = db.session.get(UserModel, record.user_id)
    if not user or not user.is_active:
        record.used_at = now
        db.session.commit()
        raise LookupError("User not found or inactive")

    record.used_at = now
    return user


def _extract_bearer_token() -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip()


def _extract_request_token() -> str | None:
    bearer = _extract_bearer_token()
    if bearer:
        return bearer
    cookie_token = request.cookies.get(_AUTH_COOKIE_NAME, "")
    return cookie_token.strip() or None


def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_request_token()
        if not token:
            return jsonify({"status": "error", "message": "Authentication required"}), 401

        try:
            user_id = _decode_token(token)
        except SignatureExpired:
            return jsonify({"status": "error", "message": "Token expired"}), 401
        except BadSignature:
            return jsonify({"status": "error", "message": "Invalid token"}), 401

        user = db.session.get(UserModel, user_id)
        if not user or not user.is_active:
            return jsonify({"status": "error", "message": "User not found or inactive"}), 401

        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = getattr(g, "current_user", None)
        if not user:
            return jsonify({"status": "error", "message": "Authentication required"}), 401
        if getattr(user, "role", None) != "admin":
            return jsonify({"success": False, "message": "Admin access required"}), 403
        return fn(*args, **kwargs)

    return wrapper


@auth_api.route("/register", methods=["POST"])
@limiter.limit("5 per minute; 20 per hour")
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not username or not email or not password:
        return jsonify({"status": "error", "message": "username, email, password are required"}), 400

    if len(username) > 80:
        return jsonify({"status": "error", "message": "Username must not exceed 80 characters"}), 400
    if len(email) > 120:
        return jsonify({"status": "error", "message": "Email must not exceed 120 characters"}), 400
    if len(password) < 8:
        return jsonify({"status": "error", "message": "Password must be at least 8 characters"}), 400

    if UserModel.query.filter_by(username=username).first():
        return jsonify({"status": "error", "message": "Username already exists"}), 409

    if UserModel.query.filter_by(email=email).first():
        return jsonify({"status": "error", "message": "Email already exists"}), 409

    user = UserModel(
        username=username,
        email=email,
        password=generate_password_hash(password),
        role="user",
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()

    token = _make_token(user)
    response = make_response(jsonify({
        "status": "success",
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        },
    }), 201)
    return _set_auth_cookie(response, token)


@auth_api.route("/login", methods=["POST"])
@limiter.limit("10 per minute; 50 per hour")
def login():
    data = request.get_json(silent=True) or {}
    identity = str(data.get("identity", data.get("email", ""))).strip()
    password = str(data.get("password", ""))

    if not identity or not password:
        return jsonify({"status": "error", "message": "identity/email and password are required"}), 400

    user = UserModel.query.filter_by(email=identity.lower()).first()
    if not user:
        user = UserModel.query.filter_by(username=identity).first()

    if not user or not check_password_hash(user.password, password):
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401

    if not user.is_active:
        return jsonify({"status": "error", "message": "User is inactive"}), 403

    token = _make_token(user)
    response = make_response(jsonify({
        "status": "success",
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        },
    }))
    return _set_auth_cookie(response, token)


@auth_api.route("/refresh", methods=["POST"])
@auth_required
@limiter.limit("20 per hour")
def refresh():
    token = _make_token(g.current_user)
    response = make_response(jsonify({"status": "success", "token": token}))
    return _set_auth_cookie(response, token)


@auth_api.route("/forgot-password", methods=["POST"])
@limiter.limit("5 per hour")
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    if not email:
        return jsonify({"status": "error", "message": "email is required"}), 400

    user = UserModel.query.filter_by(email=email).first()
    if not user:
        return jsonify({"status": "error", "message": "No account found with that email address."}), 404
    if not user.is_active:
        return jsonify({"status": "error", "message": "This account is no longer active. Please contact the administrator."}), 403

    reset_token = _issue_reset_token(user)

    payload = {
        "status": "success",
        "message": "If this email is registered, a password reset code has been sent.",
    }
    if _allow_reset_token_fallback():
        payload["reset_token"] = reset_token
    return jsonify(payload)


@auth_api.route("/reset-password", methods=["POST"])
@limiter.limit("10 per hour")
def reset_password():
    data = request.get_json(silent=True) or {}
    token = _normalize_reset_token(data.get("token", ""))
    new_password = str(data.get("new_password", ""))

    if not token:
        return jsonify({"status": "error", "message": "token is required"}), 400

    try:
        user = _consume_reset_token(token)
    except SignatureExpired:
        return jsonify({"status": "error", "message": "Reset token expired"}), 401
    except BadSignature:
        return jsonify({"status": "error", "message": "Invalid reset token"}), 401
    except LookupError:
        return jsonify({"status": "error", "message": "User not found or inactive"}), 404

    user.password = generate_password_hash(new_password)
    PasswordResetTokenModel.query.filter_by(user_id=user.id, used_at=None).delete()
    db.session.commit()

    fresh_token = _make_token(user)
    response = make_response(jsonify({"status": "success", "message": "Password reset successfully", "token": fresh_token}))
    return _set_auth_cookie(response, fresh_token)
```

---

## 7) Quick file map for your slide speaking

- Auth + token + role:
  [backend/app/presentation/api/auth_api.py](../backend/app/presentation/api/auth_api.py)
- App bootstrap security (CORS, headers, Socket room):
  [backend/app/__init__.py](../backend/app/__init__.py)
- Rate limit extension:
  [backend/app/extensions/limiter.py](../backend/app/extensions/limiter.py)
- Production secrets and TLS config:
  [backend/app/config/settings.py](../backend/app/config/settings.py)
- Reset token DB model:
  [backend/app/infrastructure/persistence/models/password_reset_token_model.py](../backend/app/infrastructure/persistence/models/password_reset_token_model.py)
- MQTT extension availability logic:
  [backend/app/extensions/mqtt.py](../backend/app/extensions/mqtt.py)

End of document.
