# app/presentation/api/automation_api.py
# ==========================================================
# CRUD API for Schedules and Automations
# ==========================================================
import logging
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request
from app.extensions.database import db
from app.extensions.limiter import limiter
from app.presentation.api.auth_api import auth_required

logger = logging.getLogger(__name__)

automation_api = Blueprint("automation_api", __name__, url_prefix="/api/automation")


# ----------------------------------------------------------
# SCHEDULES
# ----------------------------------------------------------

@automation_api.route("/schedules", methods=["GET"])
@auth_required
def list_schedules():
    from app.infrastructure.persistence.models.schedule_model import ScheduleModel
    schedules = ScheduleModel.query.filter_by(created_by=g.current_user.id).all()
    return jsonify({
        "success": True,
        "data": [
            {
                "id": s.id,
                "device_id": s.device_id,
                "action": s.action,
                "cron_expr": s.cron_expr,
                "is_active": s.is_active,
                "label": s.label,
                "remind_only": bool(getattr(s, 'remind_only', False)),
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in schedules
        ]
    })


@automation_api.route("/schedules", methods=["POST"])
@auth_required
@limiter.limit("30 per hour")
def create_schedule():
    from app.infrastructure.persistence.models.schedule_model import ScheduleModel
    data = request.get_json(silent=True) or {}

    device_id = data.get("device_id")
    action = data.get("action")
    cron_expr = data.get("cron_expr")
    label = str(data.get("label", "")).strip() or None
    remind_only = bool(data.get("remind_only", False))

    if not device_id or not action or not cron_expr:
        return jsonify({"success": False, "message": "device_id, action, cron_expr are required"}), 400

    # Validate cron
    try:
        from apscheduler.triggers.cron import CronTrigger
        CronTrigger.from_crontab(cron_expr)
    except Exception:
        return jsonify({"success": False, "message": f"Invalid cron expression: {cron_expr}"}), 400

    schedule = ScheduleModel(
        device_id=device_id,
        action=action if isinstance(action, dict) else {"value": str(action)},
        cron_expr=cron_expr,
        is_active=True,
        label=label,
        remind_only=remind_only,
        created_by=g.current_user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(schedule)
    db.session.commit()

    # Reload scheduler so the new schedule fires immediately
    try:
        from app.scheduler import _scheduler, _reload_schedules
        from flask import current_app
        if _scheduler and _scheduler.running:
            _reload_schedules(current_app._get_current_object(), _scheduler)
    except Exception as exc:
        logger.warning("Scheduler reload failed after create_schedule: %s", exc)

    return jsonify({"success": True, "id": schedule.id}), 201


@automation_api.route("/schedules/<int:schedule_id>", methods=["PATCH"])
@auth_required
def toggle_schedule(schedule_id):
    from app.infrastructure.persistence.models.schedule_model import ScheduleModel
    schedule = db.session.get(ScheduleModel, schedule_id)
    if not schedule or schedule.created_by != g.current_user.id:
        return jsonify({"success": False, "message": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        schedule.is_active = bool(data["is_active"])
    if "label" in data:
        schedule.label = str(data["label"]).strip() or None
    if "remind_only" in data:
        schedule.remind_only = bool(data["remind_only"])
    if "cron_expr" in data:
        cron_expr = str(data["cron_expr"]).strip()
        try:
            from apscheduler.triggers.cron import CronTrigger
            CronTrigger.from_crontab(cron_expr)
            schedule.cron_expr = cron_expr
        except Exception:
            return jsonify({"success": False, "message": f"Invalid cron expression: {cron_expr}"}), 400
    if "action" in data:
        action = data["action"]
        schedule.action = action if isinstance(action, dict) else {"value": str(action)}
    db.session.commit()

    try:
        from app.scheduler import _scheduler, _reload_schedules
        from flask import current_app
        if _scheduler and _scheduler.running:
            _reload_schedules(current_app._get_current_object(), _scheduler)
    except Exception as exc:
        logger.warning("Scheduler reload failed after toggle_schedule: %s", exc)

    return jsonify({
        "success": True,
        "is_active": schedule.is_active,
        "label": schedule.label,
        "remind_only": bool(getattr(schedule, 'remind_only', False)),
    })


@automation_api.route("/schedules/<int:schedule_id>", methods=["DELETE"])
@auth_required
def delete_schedule(schedule_id):
    from app.infrastructure.persistence.models.schedule_model import ScheduleModel
    schedule = db.session.get(ScheduleModel, schedule_id)
    if not schedule or schedule.created_by != g.current_user.id:
        return jsonify({"success": False, "message": "Not found"}), 404

    db.session.delete(schedule)
    db.session.commit()

    try:
        from app.scheduler import _scheduler
        if _scheduler and _scheduler.running:
            job = _scheduler.get_job(f"schedule_{schedule_id}")
            if job:
                job.remove()
    except Exception as exc:
        logger.warning("Scheduler job removal failed for schedule %d: %s", schedule_id, exc)

    return jsonify({"success": True})


# ----------------------------------------------------------
# AUTOMATIONS
# ----------------------------------------------------------

@automation_api.route("/automations", methods=["GET"])
@auth_required
def list_automations():
    from app.infrastructure.persistence.models.automation_model import AutomationModel
    from app.infrastructure.persistence.models.device_model import Device

    automations = AutomationModel.query.join(
        Device, AutomationModel.trigger_device_id == Device.id
    ).filter(Device.user_id == g.current_user.id).all()

    return jsonify({
        "success": True,
        "data": [
            {
                "id": a.id,
                "name": a.name,
                "trigger_device_id": a.trigger_device_id,
                "trigger_condition": a.trigger_condition,
                "action_device_id": a.action_device_id,
                "action_payload": a.action_payload,
                "is_active": a.is_active,
            }
            for a in automations
        ]
    })


@automation_api.route("/automations", methods=["POST"])
@auth_required
@limiter.limit("30 per hour")
def create_automation():
    from app.infrastructure.persistence.models.automation_model import AutomationModel
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    trigger_device_id = data.get("trigger_device_id")
    trigger_condition = str(data.get("trigger_condition", "")).strip()
    action_device_id = data.get("action_device_id")
    action_payload = data.get("action_payload")

    if not all([name, trigger_device_id, trigger_condition, action_device_id, action_payload]):
        return jsonify({"success": False, "message": "All fields are required"}), 400

    automation = AutomationModel(
        name=name,
        trigger_device_id=trigger_device_id,
        trigger_condition=trigger_condition,
        action_device_id=action_device_id,
        action_payload=action_payload if isinstance(action_payload, dict) else {"value": str(action_payload)},
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(automation)
    db.session.commit()
    return jsonify({"success": True, "id": automation.id}), 201


@automation_api.route("/automations/<int:auto_id>", methods=["PATCH"])
@auth_required
def toggle_automation(auto_id):
    from app.infrastructure.persistence.models.automation_model import AutomationModel
    from app.infrastructure.persistence.models.device_model import Device
    automation = (
        AutomationModel.query
        .join(Device, AutomationModel.trigger_device_id == Device.id)
        .filter(AutomationModel.id == auto_id, Device.user_id == g.current_user.id)
        .first()
    )
    if not automation:
        return jsonify({"success": False, "message": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        automation.is_active = bool(data["is_active"])
        db.session.commit()

    return jsonify({"success": True, "is_active": automation.is_active})


@automation_api.route("/automations/<int:auto_id>", methods=["DELETE"])
@auth_required
def delete_automation(auto_id):
    from app.infrastructure.persistence.models.automation_model import AutomationModel
    from app.infrastructure.persistence.models.device_model import Device
    automation = (
        AutomationModel.query
        .join(Device, AutomationModel.trigger_device_id == Device.id)
        .filter(AutomationModel.id == auto_id, Device.user_id == g.current_user.id)
        .first()
    )
    if not automation:
        return jsonify({"success": False, "message": "Not found"}), 404

    db.session.delete(automation)
    db.session.commit()
    return jsonify({"success": True})
