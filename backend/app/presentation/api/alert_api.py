# app/presentation/api/alert_api.py
import html
import logging
import os
from datetime import datetime, timezone

from flask import Blueprint, jsonify, g, request
from werkzeug.utils import secure_filename

from app.extensions.database import db
from app.wiring import container
from app.presentation.api.auth_api import auth_required, admin_required
from app.extensions.limiter import limiter
from app.usecases.sensor_usecase import SensorUseCase

alert_api = Blueprint("alert_api", __name__)
logger = logging.getLogger(__name__)

_MAX_SOS_AUDIO_BYTES = 5 * 1024 * 1024
_MAX_SOS_AUDIO_SECONDS = 30
_ALLOWED_SOS_AUDIO_MIMETYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/x-m4a",
    "audio/aac",
    "application/octet-stream",
}
_ALLOWED_SOS_AUDIO_EXTENSIONS = {".webm", ".ogg", ".wav", ".mp3", ".m4a", ".mp4", ".aac"}


def _public_delivery_summary(delivery: dict | None) -> dict:
    return {"sent": bool(delivery and delivery.get("sent"))}


def _build_sos_email_html(username: str, user_email: str, note: str, audio_attachment: dict | None) -> str:
        escaped_username = html.escape(username)
        escaped_email = html.escape(user_email)
        escaped_note = html.escape(note or "No extra note")
        attachment_name = html.escape(audio_attachment["filename"]) if audio_attachment else "No voice note attached"
        attachment_badge = "Voice note attached" if audio_attachment else "No voice note"
        attachment_color = "#dc2626" if audio_attachment else "#6b7280"
        return f"""
<html>
    <body style=\"margin:0;padding:24px;background:#fff7ed;font-family:Segoe UI,Arial,sans-serif;color:#111827;\">
        <div style=\"max-width:640px;margin:0 auto;background:#ffffff;border:1px solid #fed7aa;border-radius:18px;overflow:hidden;\">
            <div style=\"background:#b91c1c;color:#ffffff;padding:16px 24px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;\">SOS Emergency Alert</div>
            <div style=\"padding:24px;\">
                <div style=\"display:inline-block;margin-bottom:16px;padding:6px 12px;border-radius:999px;background:{attachment_color};color:#ffffff;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;\">{attachment_badge}</div>
                <p style=\"margin:0 0 12px;font-size:15px;line-height:1.6;\"><strong>User:</strong> {escaped_username}</p>
                <p style=\"margin:0 0 12px;font-size:15px;line-height:1.6;\"><strong>User email:</strong> {escaped_email}</p>
                <div style=\"margin:0 0 16px;padding:14px 16px;background:#fff1f2;border:1px solid #fecdd3;border-radius:12px;\">
                    <div style=\"margin-bottom:6px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#9f1239;\">Emergency note</div>
                    <div style=\"font-size:15px;line-height:1.6;color:#111827;\">{escaped_note}</div>
                </div>
                <div style=\"padding:14px 16px;background:#f8fafc;border:1px solid #e5e7eb;border-radius:12px;\">
                    <div style=\"margin-bottom:6px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#475569;\">Voice attachment</div>
                    <div style=\"font-size:14px;line-height:1.6;color:#0f172a;\">{attachment_name}</div>
                </div>
            </div>
        </div>
    </body>
</html>
""".strip()


def _extract_sos_note() -> str:
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        return str(request.form.get("note", "")).strip()[:200]

    body = request.get_json(silent=True) or {}
    return str(body.get("note", "")).strip()[:200]


def _extract_sos_audio_attachment() -> dict | None:
    audio_file = request.files.get("audio")
    if not audio_file or not audio_file.filename:
        return None

    filename = secure_filename(audio_file.filename) or "sos-voice-note.webm"
    ext = os.path.splitext(filename)[1].lower()
    mimetype = str(audio_file.mimetype or "application/octet-stream").strip().lower()
    if mimetype not in _ALLOWED_SOS_AUDIO_MIMETYPES and ext not in _ALLOWED_SOS_AUDIO_EXTENSIONS:
        raise ValueError("Unsupported SOS audio format")

    content = audio_file.read()
    if not content:
        return None
    if len(content) > _MAX_SOS_AUDIO_BYTES:
        raise ValueError("SOS audio recording must be 5 MB or smaller")

    normalized_mimetype = mimetype if mimetype in _ALLOWED_SOS_AUDIO_MIMETYPES else "application/octet-stream"
    return {
        "filename": filename,
        "content": content,
        "mimetype": normalized_mimetype,
    }


@alert_api.route("/alerts", methods=["GET"], strict_slashes=False)
@auth_required
def get_alerts():
    """Return alert history for the current authenticated user with pagination."""
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        offset = max(int(request.args.get("offset", 0)), 0)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "limit and offset must be integers"}), 400

    level = str(request.args.get("level", "")).strip().lower() or None
    if level and level not in {"info", "warning", "critical"}:
        return jsonify({"success": False, "message": "level must be one of info, warning, critical"}), 400

    unread_raw = str(request.args.get("unread", "")).strip().lower()
    unread_only = unread_raw in {"1", "true", "yes"}
    if unread_raw and unread_raw not in {"0", "1", "true", "false", "yes", "no"}:
        return jsonify({"success": False, "message": "unread must be a boolean"}), 400

    device_code = str(request.args.get("device_code", "")).strip() or None
    query = str(request.args.get("q", "")).strip() or None
    sort = str(request.args.get("sort", "newest")).strip().lower() or "newest"
    if sort not in {"newest", "oldest"}:
        return jsonify({"success": False, "message": "sort must be newest or oldest"}), 400

    since = None
    since_raw = str(request.args.get("since", "")).strip()
    if since_raw:
        try:
            since = datetime.fromisoformat(since_raw.replace("Z", "+00:00"))
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
        except ValueError:
            return jsonify({"success": False, "message": "since must be a valid ISO-8601 datetime"}), 400

    usecase = container.alert_usecase()
    alerts = usecase.get_all_alerts(
        user_id=g.current_user.id,
        limit=limit,
        offset=offset,
        level=level,
        unread_only=unread_only,
        device_code=device_code,
        query=query,
        since=since,
        sort=sort,
    )
    total = usecase.count_filtered_alerts(
        user_id=g.current_user.id,
        level=level,
        unread_only=unread_only,
        device_code=device_code,
        query=query,
        since=since,
    )
    summary = usecase.get_filtered_summary(
        user_id=g.current_user.id,
        level=level,
        unread_only=unread_only,
        device_code=device_code,
        query=query,
        since=since,
    )
    unread = usecase.count_unread(user_id=g.current_user.id)
    return jsonify({"success": True, "data": alerts, "unread": unread, "total": total, "summary": summary}), 200


@alert_api.route("/alerts/<int:alert_id>", methods=["DELETE"], strict_slashes=False)
@auth_required
@limiter.limit("120 per minute")
def delete_alert(alert_id):
    """Delete a specific alert (scoped to current user)."""
    usecase = container.alert_usecase()
    ok = usecase.delete_alert(alert_id, user_id=g.current_user.id)
    if not ok:
        return jsonify({"success": False, "message": "Alert not found"}), 404
    return jsonify({"success": True}), 200


@alert_api.route("/alerts/read", methods=["DELETE"], strict_slashes=False)
@auth_required
@limiter.limit("10 per minute")
def clear_read_alerts():
    """Delete all read alerts for the current user."""
    usecase = container.alert_usecase()
    deleted = usecase.clear_read_alerts(user_id=g.current_user.id)
    return jsonify({"success": True, "deleted": deleted}), 200


@alert_api.route("/alerts/views", methods=["GET"], strict_slashes=False)
@auth_required
def get_alert_saved_views():
    usecase = container.alert_saved_view_usecase()
    views = usecase.get_views(user_id=g.current_user.id)
    return jsonify({"success": True, "data": views}), 200


@alert_api.route("/alerts/views", methods=["PUT"], strict_slashes=False)
@auth_required
@limiter.limit("60 per minute")
def replace_alert_saved_views():
    body = request.get_json(silent=True) or {}
    views = body.get("views")
    if not isinstance(views, list):
        return jsonify({"success": False, "message": "views must be a list"}), 400

    usecase = container.alert_saved_view_usecase()
    try:
        normalized = usecase.replace_views(user_id=g.current_user.id, views=views)
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception:
        db.session.rollback()
        logger.error("Failed to save alert views", exc_info=True)
        return jsonify({"success": False, "message": "Failed to save alert views"}), 500

    return jsonify({"success": True, "data": normalized}), 200


@alert_api.route("/alerts/views/stats", methods=["GET"], strict_slashes=False)
@auth_required
@admin_required
def get_alert_saved_views_stats():
    try:
        limit = min(max(int(request.args.get("limit", 10)), 1), 50)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "limit must be an integer"}), 400

    usecase = container.alert_saved_view_usecase()
    stats = usecase.get_stats(limit=limit)
    return jsonify({"success": True, "data": stats}), 200


@alert_api.route("/alerts/sos", methods=["POST"], strict_slashes=False)
@auth_required
@limiter.limit("10 per minute")
def trigger_sos():
    """Trigger an SOS emergency alert from the frontend dashboard."""
    note = _extract_sos_note()
    try:
        audio_attachment = _extract_sos_audio_attachment()
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    message = f"🆘 SOS EMERGENCY triggered by {g.current_user.username}"
    if note:
        message += f" — {note}"
    usecase = container.alert_usecase()
    try:
        alert = usecase.create_alert(
            device_code="SOS",
            message=message,
            level="critical",
            user_id=g.current_user.id,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.error("Failed to persist SOS alert", exc_info=True)
        return jsonify({"success": False, "message": "Failed to record SOS alert"}), 500

    # Send async: SOS alert is already persisted to DB; email delivery must not
    # block the HTTP response or fail the SOS acknowledgement to the user.
    notifier = container.email_notifier()
    notifier.send_async(
        subject=f"SOS Emergency: {g.current_user.username}",
        body=(
            f"Emergency SOS triggered by user: {g.current_user.username}\n"
            f"User email: {g.current_user.email}\n"
            f"Note: {note or 'No extra note'}\n"
            f"Voice note attached: {'Yes' if audio_attachment else 'No'}\n"
            f"Maximum recommended voice-note length: {_MAX_SOS_AUDIO_SECONDS} seconds\n"
        ),
        recipients=notifier.resolve_recipients(
            user_email=g.current_user.email,
            include_default_recipients=True,
        ),
        attachments=[audio_attachment] if audio_attachment else None,
        html_body=_build_sos_email_html(
            username=g.current_user.username,
            user_email=g.current_user.email,
            note=note,
            audio_attachment=audio_attachment,
        ),
    )

    return jsonify({
        "success": True,
        "alert_id": alert.id,
        "message": message,
        "delivery": {"sent": True, "async": True},
        "audio_attached": bool(audio_attachment),
    }), 201


@alert_api.route("/alerts/<int:alert_id>/read", methods=["PATCH"], strict_slashes=False)
@auth_required
@limiter.limit("120 per minute")
def mark_alert_read(alert_id):
    """Mark a specific alert as read."""
    usecase = container.alert_usecase()
    ok = usecase.mark_alert_read(alert_id, user_id=g.current_user.id)
    if not ok:
        return jsonify({"success": False, "message": "Alert not found"}), 404
    return jsonify({"success": True}), 200


@alert_api.route("/alerts/read", methods=["PATCH"], strict_slashes=False)
@auth_required
@limiter.limit("30 per minute")
def mark_alerts_read():
    """Mark multiple alerts as read for the current authenticated user."""
    body = request.get_json(silent=True) or {}
    raw_ids = body.get("ids")
    if not isinstance(raw_ids, list):
        return jsonify({"success": False, "message": "ids must be a list of alert ids"}), 400

    cleaned_ids = []
    for value in raw_ids:
        try:
            alert_id = int(value)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "ids must contain only integers"}), 400
        if alert_id > 0:
            cleaned_ids.append(alert_id)

    if not cleaned_ids:
        return jsonify({"success": False, "message": "ids must contain at least one alert id"}), 400

    usecase = container.alert_usecase()
    marked = usecase.mark_alerts_read(cleaned_ids, user_id=g.current_user.id)
    unread = usecase.count_unread(user_id=g.current_user.id)
    return jsonify({"success": True, "marked": marked, "unread": unread}), 200


@alert_api.route("/alerts/suggestions/preferences", methods=["GET"], strict_slashes=False)
@auth_required
def get_suggestion_preferences():
    pref = SensorUseCase.get_user_suggestion_pref(g.current_user.id)
    mute_until = pref.get("mute_until")
    updated_at = pref.get("updated_at")
    return jsonify({
        "success": True,
        "data": {
            "is_muted": bool(pref.get("is_muted")),
            "mute_until": mute_until.isoformat() if mute_until else None,
            "updated_at": updated_at.isoformat() if updated_at else None,
        },
    }), 200


@alert_api.route("/alerts/suggestions/preferences", methods=["PUT"], strict_slashes=False)
@auth_required
@limiter.limit("60 per minute")
def update_suggestion_preferences():
    body = request.get_json(silent=True) or {}
    mute_minutes_raw = body.get("mute_minutes", 60)
    try:
        mute_minutes = int(mute_minutes_raw)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "mute_minutes must be an integer"}), 400
    if mute_minutes < 0:
        return jsonify({"success": False, "message": "mute_minutes must be >= 0"}), 400

    mute_until = SensorUseCase.set_user_suggestion_mute(g.current_user.id, mute_minutes=mute_minutes)
    pref = SensorUseCase.get_user_suggestion_pref(g.current_user.id)
    return jsonify({
        "success": True,
        "data": {
            "is_muted": bool(pref.get("is_muted")),
            "mute_minutes": mute_minutes,
            "mute_until": mute_until.isoformat() if mute_until else None,
        },
    }), 200


@alert_api.route("/alerts/mute/preferences", methods=["GET"], strict_slashes=False)
@auth_required
def get_alert_mute_preferences():
    pref = container.alert_mute_preference_usecase().get_preference(g.current_user.id)
    updated_at = pref.get("updated_at")
    return jsonify({
        "success": True,
        "data": {
            "scope": pref.get("scope") or "none",
            "keyword": pref.get("keyword") or "",
            "is_active": bool(pref.get("is_active")),
            "updated_at": updated_at.isoformat() if updated_at else None,
        },
    }), 200


@alert_api.route("/alerts/mute/preferences", methods=["PUT"], strict_slashes=False)
@auth_required
@limiter.limit("60 per minute")
def update_alert_mute_preferences():
    body = request.get_json(silent=True) or {}
    scope = body.get("scope", "none")
    keyword = body.get("keyword", "")

    try:
        pref = container.alert_mute_preference_usecase().set_preference(
            user_id=g.current_user.id,
            scope=scope,
            keyword=keyword,
        )
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception:
        db.session.rollback()
        logger.error("Failed to save alert mute preferences", exc_info=True)
        return jsonify({"success": False, "message": "Failed to save alert mute preferences"}), 500

    updated_at = pref.get("updated_at")
    return jsonify({
        "success": True,
        "data": {
            "scope": pref.get("scope") or "none",
            "keyword": pref.get("keyword") or "",
            "is_active": bool(pref.get("is_active")),
            "updated_at": updated_at.isoformat() if updated_at else None,
        },
    }), 200


@alert_api.route("/alerts/confirm-action", methods=["POST"], strict_slashes=False)
@auth_required
@limiter.limit("120 per minute")
def confirm_suggested_action():
    body = request.get_json(silent=True) or {}
    device_code = str(body.get("device_code", "")).strip()
    value = str(body.get("value", "ON")).strip().upper() or "ON"
    if not device_code:
        return jsonify({"success": False, "message": "device_code is required"}), 400
    if value not in {"ON", "OFF"}:
        return jsonify({"success": False, "message": "value must be ON or OFF"}), 400

    result = container.device_usecase().control_device(
        {"device_code": device_code, "action": value},
        user_id=g.current_user.id,
    )
    if not result.get("success"):
        status = int(result.get("status") or 400)
        return jsonify({"success": False, "message": result.get("message") or "Device control failed"}), status

    return jsonify({"success": True, "device_code": device_code, "value": value}), 200
