import logging

from flask import Blueprint, g, jsonify, request

from app.presentation.api.auth_api import auth_required
from app.extensions.limiter import limiter
from app.wiring import container


logger = logging.getLogger(__name__)

reminder_api = Blueprint("reminder_api", __name__, url_prefix="/api/reminders")


@reminder_api.route("", methods=["GET"], strict_slashes=False)
@auth_required
def list_reminders():
    usecase = container.medicine_reminder_usecase()
    return jsonify({
        "success": True,
        "data": usecase.list_for_user(g.current_user.id),
        "email_enabled": container.email_notifier().enabled,
    }), 200


@reminder_api.route("", methods=["POST"], strict_slashes=False)
@auth_required
@limiter.limit("60 per hour")
def create_reminder():
    data = request.get_json(silent=True) or {}
    usecase = container.medicine_reminder_usecase()
    try:
        reminder = usecase.create_for_user(
            user_id=g.current_user.id,
            name=data.get("name"),
            dose=data.get("dose"),
            time_of_day=data.get("time"),
            recurrence=data.get("days"),
            notify_email=data.get("notify_email"),
        )
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception:
        logger.error("Failed to create reminder", exc_info=True)
        return jsonify({"success": False, "message": "Failed to create reminder"}), 500

    return jsonify({
        "success": True,
        "data": usecase.serialize(reminder),
    }), 201


@reminder_api.route("/<int:reminder_id>/taken", methods=["PATCH"], strict_slashes=False)
@auth_required
@limiter.limit("240 per hour")
def set_taken(reminder_id):
    data = request.get_json(silent=True) or {}
    usecase = container.medicine_reminder_usecase()
    reminder = usecase.set_taken(reminder_id, g.current_user.id, bool(data.get("taken", True)))
    if not reminder:
        return jsonify({"success": False, "message": "Reminder not found"}), 404
    return jsonify({"success": True, "data": usecase.serialize(reminder)}), 200


@reminder_api.route("/<int:reminder_id>", methods=["DELETE"], strict_slashes=False)
@auth_required
@limiter.limit("120 per hour")
def delete_reminder(reminder_id):
    usecase = container.medicine_reminder_usecase()
    if not usecase.delete(reminder_id, g.current_user.id):
        return jsonify({"success": False, "message": "Reminder not found"}), 404
    return jsonify({"success": True}), 200