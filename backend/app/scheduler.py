# app/scheduler.py
# ==========================================================
# SCHEDULE & AUTOMATION EXECUTOR
#
# Quản lý 2 loại tác vụ nền hoàn toàn khác nhau:
#
# [1] SCHEDULE (giống Calendar — theo giờ/ngày):
#     - Lưu trong ScheduleModel với cron_expr (vd: "0 7 * * *" = 7h sáng)
#     - Reload từ DB mỗi 5 phút để cập nhật khi user thêm/xóa
#     - Khi đến giờ → gửi lệnh MQTT bật/tắt thiết bị
#     - Ví dụ: "7:00 sáng mỗi ngày → bật đèn phòng ngủ"
#
# [2] AUTOMATION (theo điều kiện cảm biến — không phải giờ):
#     - Lưu trong AutomationModel với trigger_condition (vd: "value > 35")
#     - Kiểm tra mỗi 30 giây, so sánh với DeviceStatus hiện tại
#     - Nếu điều kiện thỏa → gửi lệnh MQTT đến thiết bị hành động
#     - Ví dụ: "nhiệt độ > 35°C → bật quạt"
#
# [3] MEDICINE REMINDER (nhắc thuốc):
#     - Kiểm tra mỗi 1 phút, cửa sổ ±1 phút để tránh miss
#     - Gửi email + tạo Alert khi đến giờ uống thuốc
# ==========================================================

import json
import logging
import re
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

# In-memory PIR motion tracking: {user_id: datetime_utc}
_last_pir_seen: dict = {}
# Cooldown for inactivity alerts: {user_id: datetime_utc}
_pir_alert_cooldown: dict = {}


def record_pir_motion(user_id: int) -> None:
    """Called by sensor_usecase when a PIR device fires. Thread-safe write to dict."""
    _last_pir_seen[int(user_id)] = datetime.now(timezone.utc)


# ----------------------------------------------------------
# PRIVATE: Evaluate automation trigger condition
# Examples: "value > 35", "value == 'ON'", "is_on == true"
# Uses regex matching — never eval() on user input.
# ----------------------------------------------------------
def _eval_condition(condition: str, status) -> bool:
    """Safe evaluation of trigger_condition string against a DeviceStatus object."""
    try:
        cond = condition.strip()
        value_raw = status.value if status else None
        is_on = bool(status.is_on) if status else False

        try:
            value = float(value_raw) if value_raw is not None else 0.0
        except (ValueError, TypeError):
            value = str(value_raw or "")

        # Regex-based evaluation — supports: "value OP literal" or "is_on OP literal"
        pattern = r'^(value|is_on)\s*(==|!=|>=|<=|>|<)\s*(.+)$'
        m = re.match(pattern, cond, re.IGNORECASE)
        if not m:
            logger.warning("[Scheduler] Unrecognized condition: %s", cond)
            return False

        left_token, operator, right_raw = m.group(1).lower(), m.group(2), m.group(3).strip().strip("'\"")

        left_val = value if left_token == "value" else is_on

        # Parse right side
        try:
            right_val: float | bool | str
            if right_raw.lower() in ("true", "on"):
                right_val = True
            elif right_raw.lower() in ("false", "off"):
                right_val = False
            else:
                right_val = float(right_raw)
        except ValueError:
            right_val = str(right_raw)

        ops = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">":  lambda a, b: float(a) > float(b),
            ">=": lambda a, b: float(a) >= float(b),
            "<":  lambda a, b: float(a) < float(b),
            "<=": lambda a, b: float(a) <= float(b),
        }
        result = ops[operator](left_val, right_val)
        return bool(result)
    except Exception as e:
        logger.warning("[Scheduler] Condition eval error (%s): %s", condition, e)
        return False


# ----------------------------------------------------------
# JOB: Execute a single schedule
# ----------------------------------------------------------
def _execute_schedule(app, schedule_id: int):
    """Runs in a background thread — requires app context."""
    with app.app_context():
        try:
            from app.extensions.database import db
            from app.infrastructure.persistence.models.schedule_model import ScheduleModel
            from app.infrastructure.persistence.models.device_model import Device
            from app.gateways.mqtt_publisher import MqttPublisher

            schedule = db.session.get(ScheduleModel, schedule_id)
            if not schedule or not schedule.is_active:
                return

            device = db.session.get(Device, schedule.device_id)
            if not device:
                logger.warning("[Scheduler] Schedule %d: device %d not found", schedule_id, schedule.device_id)
                return

            action = schedule.action if isinstance(schedule.action, dict) else {}
            is_on = action.get("is_on", True)
            value = action.get("value", "ON" if is_on else "OFF")

            # REMINDER MODE: emit popup to frontend instead of auto-executing
            if getattr(schedule, 'remind_only', False):
                try:
                    from app.gateways.socket_emitter import SocketEmitter
                    emitter = SocketEmitter()
                    emitter.emit("schedule_reminder", {
                        "schedule_id": schedule_id,
                        "label": schedule.label or f"Schedule #{schedule_id}",
                        "device_code": device.code,
                        "device_name": device.name,
                        "action": action,
                        "is_on": bool(is_on),
                        "value": str(value),
                    })
                    logger.info("[Scheduler] Schedule %d reminder emitted: %s → %s", schedule_id, device.code, value)
                except Exception as emit_err:
                    logger.error("[Scheduler] Schedule %d reminder emit error: %s", schedule_id, emit_err)
                return

            # AUTO-EXECUTE MODE: send MQTT command immediately
            payload = str(value)
            mqtt = MqttPublisher()
            mqtt.send_device_command(device.code, payload)

            # Update DeviceStatus
            from app.infrastructure.persistence.models.device_status_model import DeviceStatus
            status = DeviceStatus.query.filter_by(device_id=device.id).first()
            if status:
                status.is_on = bool(is_on)
                status.value = payload
                status.updated_at = datetime.now(timezone.utc)
                db.session.commit()

            logger.info("[Scheduler] Schedule %d executed: %s → %s", schedule_id, device.code, payload)

        except Exception as e:
            logger.error("[Scheduler] Schedule %d error: %s", schedule_id, e)


# ----------------------------------------------------------
# JOB: Check all automations (runs every 30s)
# ----------------------------------------------------------
def _check_automations(app):
    """Check all active automation rules and fire any whose condition is met."""
    with app.app_context():
        try:
            from app.extensions.database import db
            from app.infrastructure.persistence.models.automation_model import AutomationModel
            from app.infrastructure.persistence.models.device_model import Device
            from app.infrastructure.persistence.models.device_status_model import DeviceStatus
            from app.gateways.mqtt_publisher import MqttPublisher

            automations = AutomationModel.query.filter_by(is_active=True).all()
            if not automations:
                return

            mqtt = MqttPublisher()
            fired = []  # track (action_device, is_on) for Socket.IO emit after commit

            for auto in automations:
                trigger_device = db.session.get(Device, auto.trigger_device_id)
                if not trigger_device:
                    continue

                trigger_status = DeviceStatus.query.filter_by(device_id=trigger_device.id).first()
                if not _eval_condition(auto.trigger_condition, trigger_status):
                    continue

                # Condition met — execute action
                action_device = db.session.get(Device, auto.action_device_id)
                if not action_device:
                    continue

                action_data = auto.action_payload if isinstance(auto.action_payload, dict) else {}

                is_on = action_data.get("is_on", True)
                value = action_data.get("value", "ON" if is_on else "OFF")
                payload = str(value)

                mqtt.send_device_command(action_device.code, payload)

                action_status = DeviceStatus.query.filter_by(device_id=action_device.id).first()
                if action_status:
                    action_status.is_on = bool(is_on)
                    action_status.value = payload
                    action_status.updated_at = datetime.now(timezone.utc)
                    fired.append((action_device, bool(is_on)))

                logger.info(
                    "[Scheduler] Automation '%s': %s (%s) → %s → %s",
                    auto.name, trigger_device.code, auto.trigger_condition,
                    action_device.code, payload,
                )

            db.session.commit()

            # Emit Socket.IO for every fired rule so the dashboard updates immediately
            # without waiting for an ESP32 status reply (absent in demo/offline mode).
            from app.extensions.socketio import socketio as _sio
            for action_device, device_is_on in fired:
                _sio.emit("device_status", {
                    "event":       "DEVICE_UPDATED",
                    "device_code": action_device.code,
                    "device_name": action_device.name,
                    "is_on":       device_is_on,
                    "value":       None,
                }, room=f"user_{action_device.user_id}")

        except Exception as e:
            logger.error("[Scheduler] Automation check error: %s", e)


def _dispatch_medicine_reminders(app):
    """Dispatch due medicine reminders using backend email + alert channels."""
    with app.app_context():
        try:
            from app.wiring import container

            dispatched = container.medicine_reminder_usecase().dispatch_due_reminders()
            if dispatched:
                logger.info("[Scheduler] Dispatched %d medicine reminder(s)", dispatched)
        except Exception as e:
            logger.error("[Scheduler] Medicine reminder dispatch error: %s", e)


# ----------------------------------------------------------
# JOB: Reload schedules from DB (runs at startup and every 5 min)
# ----------------------------------------------------------
def _reload_schedules(app, scheduler: BackgroundScheduler):
    """Drop all existing schedule jobs and reload from DB."""
    with app.app_context():
        try:
            from app.infrastructure.persistence.models.schedule_model import ScheduleModel

            # Remove old schedule jobs (keep automation + reminder jobs)
            for job in scheduler.get_jobs():
                if job.id.startswith("schedule_"):
                    job.remove()

            schedules = ScheduleModel.query.filter_by(is_active=True).all()
            for s in schedules:
                try:
                    trigger = CronTrigger.from_crontab(s.cron_expr, timezone="Asia/Ho_Chi_Minh")
                    scheduler.add_job(
                        func=_execute_schedule,
                        trigger=trigger,
                        args=[app, s.id],
                        id=f"schedule_{s.id}",
                        replace_existing=True,
                        misfire_grace_time=60,
                    )
                    logger.debug("[Scheduler] Loaded schedule %d: %s", s.id, s.cron_expr)
                except Exception as e:
                    logger.warning("[Scheduler] Invalid cron for schedule %d: %s", s.id, e)

            logger.info("[Scheduler] Loaded %d active schedules from DB", len(schedules))

        except Exception as e:
            logger.error("[Scheduler] Reload schedules error: %s", e)


# ----------------------------------------------------------
# PIR INACTIVITY CHECK
# Alert caregiver if no motion during daytime hours > threshold
# ----------------------------------------------------------
def _check_pir_inactivity(app):
    THRESHOLD_MIN   = 30   # minutes of silence before alert
    ACTIVE_H_START  = 7    # 07:00 local
    ACTIVE_H_END    = 22   # 22:00 local
    COOLDOWN_MIN    = 60   # don't re-alert same user within 60 min

    with app.app_context():
        try:
            local_hour = datetime.now().hour
            if not (ACTIVE_H_START <= local_hour < ACTIVE_H_END):
                return

            from app.infrastructure.persistence.models.device_model import Device
            from app.infrastructure.persistence.models.device_status_model import DeviceStatus
            from app.wiring import container

            pir_devices = Device.query.filter_by(device_type='pir', is_deleted=False).all()
            now_utc = datetime.now(timezone.utc)

            for device in pir_devices:
                uid = device.user_id
                last_seen = _last_pir_seen.get(uid)

                if last_seen is None:
                    status = DeviceStatus.query.filter_by(device_id=device.id).first()
                    if status and status.updated_at:
                        dt = status.updated_at
                        last_seen = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
                    else:
                        continue

                elapsed_min = (now_utc - last_seen).total_seconds() / 60.0
                if elapsed_min < THRESHOLD_MIN:
                    continue

                cooldown_until = _pir_alert_cooldown.get(uid)
                if cooldown_until and (now_utc - cooldown_until).total_seconds() < COOLDOWN_MIN * 60:
                    continue

                alert_uc = container.alert_usecase()
                alert_uc.create_alert(
                    device_code=device.code,
                    message=(
                        f"No movement detected for {int(elapsed_min)} min — "
                        f"please check on the resident ({device.name})."
                    ),
                    level="warning",
                    user_id=uid,
                )
                _pir_alert_cooldown[uid] = now_utc
                logger.info("[PIR] Inactivity alert for user %s: %d min since last motion", uid, int(elapsed_min))

        except Exception as exc:
            logger.error("[PIR] Inactivity check failed: %s", exc)


# ----------------------------------------------------------
# PUBLIC: init_scheduler(app)
# ----------------------------------------------------------
def init_scheduler(app):
    """Initialize APScheduler and register it into the Flask app lifecycle."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.warning("[Scheduler] Already running, skipping init")
        return

    _scheduler = BackgroundScheduler(
        job_defaults={
            "coalesce": True,        # Skip missed firings instead of catching up
            "max_instances": 1,
        },
        timezone="Asia/Ho_Chi_Minh",
    )

    # Check automations every 30 seconds
    _scheduler.add_job(
        func=_check_automations,
        trigger="interval",
        seconds=30,
        args=[app],
        id="automation_check",
        replace_existing=True,
    )

    # PIR inactivity check every 10 minutes
    _scheduler.add_job(
        func=_check_pir_inactivity,
        trigger="interval",
        minutes=10,
        args=[app],
        id="pir_inactivity_check",
        replace_existing=True,
    )

    _scheduler.add_job(
        func=_dispatch_medicine_reminders,
        trigger="interval",
        minutes=1,
        args=[app],
        id="medicine_reminder_dispatch",
        replace_existing=True,
    )

    # Reload schedules from DB every 5 minutes to pick up user changes
    _scheduler.add_job(
        func=_reload_schedules,
        trigger="interval",
        minutes=5,
        args=[app, _scheduler],
        id="schedule_reload",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("[Scheduler] APScheduler started")

    # Load schedules immediately on startup
    _reload_schedules(app, _scheduler)

    return _scheduler
