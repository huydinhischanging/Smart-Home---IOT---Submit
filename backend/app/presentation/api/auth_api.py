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


def _build_reset_email_html(user: UserModel, reset_token: str) -> str:
        escaped_username = html.escape(user.username)
        escaped_email = html.escape(user.email)
        escaped_token = html.escape(reset_token)
        return f"""
<html>
    <body style=\"margin:0;padding:24px;background:#f4f6fb;font-family:Segoe UI,Arial,sans-serif;color:#111827;\">
        <div style=\"max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;\">
            <div style=\"background:#fbbf24;color:#111827;padding:16px 24px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;\">Batman OS Password Reset</div>
            <div style=\"padding:24px;line-height:1.65;font-size:15px;\">
                <p style=\"margin:0 0 12px;\">Hello {escaped_username},</p>
                <p style=\"margin:0 0 12px;\">A password reset was requested for account email: <strong>{escaped_email}</strong>.</p>
                <p style=\"margin:0 0 12px;\">Only the most recent reset code is valid. Requesting a new email will invalidate older codes.</p>
                <p style=\"margin:0 0 10px;\">Use this code within 30 minutes:</p>
                <div style=\"margin:0 0 16px;padding:16px 18px;background:#111827;border-radius:12px;border:1px solid #fbbf24;color:#f9fafb;font-family:Consolas,'Courier New',monospace;font-size:22px;font-weight:700;letter-spacing:.04em;word-break:break-all;text-align:center;user-select:all;\">{escaped_token}</div>
                <p style=\"margin:0 0 8px;color:#4b5563;font-size:14px;\">Copy the code exactly as shown above and paste it into the reset form.</p>
                <p style=\"margin:0;color:#6b7280;font-size:13px;\">If you did not request this, you can ignore this email.</p>
            </div>
        </div>
    </body>
</html>
""".strip()


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


def _serialize_user(user: UserModel) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _email_notifier():
    return container.email_notifier()


def _public_delivery_summary(delivery: dict | None) -> dict:
    return {"sent": bool(delivery and delivery.get("sent"))}


def _validate_username(username: str):
    if not username:
        return jsonify({"status": "error", "message": "new_username is required"}), 400
    if len(username) > 80:
        return jsonify({"status": "error", "message": "Username must not exceed 80 characters"}), 400
    return None


def _validate_password_length(password: str):
    if len(password) < 8:
        return jsonify({"status": "error", "message": "Password must be at least 8 characters"}), 400
    if not any(c.isupper() for c in password):
        return jsonify({"status": "error", "message": "Password must contain at least one uppercase letter"}), 400
    if not any(c.islower() for c in password):
        return jsonify({"status": "error", "message": "Password must contain at least one lowercase letter"}), 400
    if not any(c.isdigit() for c in password):
        return jsonify({"status": "error", "message": "Password must contain at least one digit"}), 400
    return None


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


@auth_api.route("/me", methods=["GET"])
@auth_required
def me():
    user = g.current_user
    return jsonify({
        "status": "success",
        "user": _serialize_user(user),
    })


@auth_api.route("/refresh", methods=["POST"])
@auth_required
@limiter.limit("20 per hour")
def refresh():
    """Issue a fresh token for the currently authenticated user."""
    token = _make_token(g.current_user)
    response = make_response(jsonify({"status": "success", "token": token}))
    return _set_auth_cookie(response, token)


@auth_api.route("/logout", methods=["POST"])
def logout():
    response = make_response(jsonify({"status": "success", "message": "Logged out"}))
    return _clear_auth_cookie(response)


@auth_api.route("/profile", methods=["PATCH"])
@auth_required
@limiter.limit("10 per hour")
def update_profile():
    data = request.get_json(silent=True) or {}
    new_username = str(data.get("new_username", data.get("username", ""))).strip()
    current_password = str(data.get("current_password", ""))

    username_error = _validate_username(new_username)
    if username_error:
        return username_error
    if not current_password:
        return jsonify({"status": "error", "message": "current_password is required"}), 400
    if not check_password_hash(g.current_user.password, current_password):
        return jsonify({"status": "error", "message": "Current password is incorrect"}), 403
    if new_username == g.current_user.username:
        return jsonify({"status": "error", "message": "New username must be different"}), 400

    existing = UserModel.query.filter_by(username=new_username).first()
    if existing and existing.id != g.current_user.id:
        return jsonify({"status": "error", "message": "Username already exists"}), 409

    g.current_user.username = new_username
    db.session.commit()
    fresh_token = _make_token(g.current_user)
    response = make_response(jsonify({
        "status": "success",
        "message": "Username updated successfully",
        "user": _serialize_user(g.current_user),
        "token": fresh_token,
    }))
    return _set_auth_cookie(response, fresh_token)


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

    generic_message = "If this email is registered, a password reset code has been sent."
    reset_token = _issue_reset_token(user)
    notifier = _email_notifier()
    recipients = notifier.resolve_recipients(user_email=user.email)
    delivery = notifier.send_message(
        subject="Batman OS password reset",
        body=(
            f"Hello {user.username},\n\n"
            f"Password reset requested for account email: {user.email}\n\n"
            "Only the most recent reset code is valid. Requesting a new email will invalidate older codes.\n\n"
            f"Use this password reset code within 30 minutes:\n\n{reset_token}\n\n"
            "Copy the code exactly as shown and paste it into the reset form.\n\n"
            "If you did not request this, you can ignore this email."
        ),
        recipients=recipients,
        html_body=_build_reset_email_html(user, reset_token),
    )

    payload = {
        "status": "success",
        "message": generic_message,
    }
    if not delivery.get("sent") and _allow_reset_token_fallback():
        payload["reset_token"] = reset_token
        payload["message"] = "Password reset email is unavailable. Use the returned reset token in a trusted environment."
    return jsonify(payload)


@auth_api.route("/reset-password", methods=["POST"])
@limiter.limit("10 per hour")
def reset_password():
    data = request.get_json(silent=True) or {}
    token = _normalize_reset_token(data.get("token", ""))
    new_password = str(data.get("new_password", ""))

    if not token:
        return jsonify({"status": "error", "message": "token is required"}), 400
    password_error = _validate_password_length(new_password)
    if password_error:
        return password_error

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


@auth_api.route("/account", methods=["DELETE"])
@auth_required
@limiter.limit("5 per hour")
def cancel_account():
    data = request.get_json(silent=True) or {}
    current_password = str(data.get("current_password", ""))

    if not current_password:
        return jsonify({"status": "error", "message": "current_password is required"}), 400
    if not check_password_hash(g.current_user.password, current_password):
        return jsonify({"status": "error", "message": "Current password is incorrect"}), 403

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    user = g.current_user
    user.is_active = False
    user.username = f"deleted-user-{user.id}-{timestamp}"
    user.email = f"deleted-user-{user.id}-{timestamp}@invalid.local"
    user.password = generate_password_hash(f"deleted-{user.id}-{timestamp}")
    db.session.commit()

    response = make_response(jsonify({
        "status": "success",
        "message": "Account cancelled successfully",
    }))
    return _clear_auth_cookie(response)
