#app/presentation/api/device_api.py
import logging

from flask import Blueprint, request, jsonify

from app.usecases.device_usecase import DeviceUseCase
from app.wiring import container
from app.presentation.api.auth_api import auth_required
from app.extensions.limiter import limiter
from flask import g


device_api = Blueprint(
    "device_api",
    __name__,
    url_prefix="/api/devices"
)

logger = logging.getLogger(__name__)


# ==========================================================
# RESPONSE FORMATTER
# ==========================================================
def _format_response(result: dict, default_status: int = 200):
    status_code = result.get("status", default_status)
    return jsonify(result), status_code


# ==========================================================
# 1️⃣ GET ALL / CREATE
# ==========================================================
@device_api.route("", methods=["GET", "POST", "OPTIONS"], strict_slashes=False)
@auth_required
@limiter.limit("2000 per hour; 60 per minute")
def devices():

    usecase: DeviceUseCase = container.device_usecase()
    user_id = g.current_user.id

    # GET
    if request.method == "GET":
        data = usecase.get_all_devices(user_id=user_id)
        return jsonify({
            "success": True,
            "status": "online",
            "data": data
        }), 200

    # CREATE
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or data.get("device_name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "name or device_name is required"}), 400
    if len(name) > 100:
        return jsonify({"success": False, "message": "Device name must not exceed 100 characters"}), 400
    code = str(data.get("code") or data.get("device_code") or data.get("device_id") or "").strip()
    if len(code) > 100:
        return jsonify({"success": False, "message": "Device code must not exceed 100 characters"}), 400
    data = dict(data)
    data["name"] = name
    if code:
        data["code"] = code
    result = usecase.create_device(data, user_id=user_id)

    if result.get("success"):
        container.realtime_notifier().notify_device_list_changed(user_id=user_id)

    return _format_response(result, 201)


# ==========================================================
# 2️⃣ STATUS (LEGACY SUPPORT)
# ⚠ MUST BE BEFORE /<name>
# ==========================================================
@device_api.route("/status", methods=["GET", "OPTIONS"], strict_slashes=False)
@device_api.route("/device-status", methods=["GET", "OPTIONS"], strict_slashes=False)
@auth_required
@limiter.limit("2000 per hour; 60 per minute")
def api_status():

    usecase: DeviceUseCase = container.device_usecase()
    data = usecase.get_all_devices(user_id=g.current_user.id)

    return jsonify({
        "success": True,
        "status": "online",
        "data": data
    }), 200


# ==========================================================
# 3️⃣ CONTROL
# ⚠ MUST BE BEFORE /<name>
# ==========================================================
@device_api.route("/control", methods=["POST", "OPTIONS"], strict_slashes=False)
@auth_required
@limiter.limit("120 per minute")
def control_device():
    data = request.get_json(silent=True) or {}
    device_name = str(data.get("device_name") or data.get("name") or "").strip()
    device_code = str(data.get("device_code") or data.get("code") or data.get("device_id") or "").strip()
    device_id = data.get("device_id")
    if not any([device_name, device_code, device_id is not None]):
        return jsonify({"success": False, "message": "Provide one of device_id, device_code/code, or device_name/name"}), 400
    if device_name and len(device_name) > 100:
        return jsonify({"success": False, "message": "device_name must not exceed 100 characters"}), 400
    if device_code and len(device_code) > 100:
        return jsonify({"success": False, "message": "device_code must not exceed 100 characters"}), 400
    action = str(data.get("action") or data.get("value") or "").strip()
    if not action:
        return jsonify({"success": False, "message": "action or value is required"}), 400
    # Normalize aliases so usecase can find device regardless of which key frontend used
    data = dict(data)
    if device_code:
        data["device_code"] = device_code
    if device_name:
        data["device_name"] = device_name
    usecase: DeviceUseCase = container.device_usecase()
    result = usecase.control_device(data, user_id=g.current_user.id)

    return _format_response(result)


# ==========================================================
# 3.5️⃣ CREATION SCHEMA (FOR UI/CHATBOT)
# ==========================================================
@device_api.route("/schema", methods=["GET", "OPTIONS"], strict_slashes=False)
@auth_required
@limiter.limit("2000 per hour; 60 per minute")
def device_schema():
    return jsonify({
        "success": True,
        "data": {
            "required": ["name"],
            "aliases": {
                "name": ["name", "device_name"],
                "code": ["code", "device_code", "device_id"],
                "type": ["type", "device_type"],
                "room_id": ["room_id", "location"],
            },
            "allowed_categories": [
                "sensor", "actuator", "light", "fan", "ac", "camera", "lock", "switch", "tv", "speaker", "other"
            ],
            "examples": {
                "sensor": {
                    "device_name": "Do am phong ngu",
                    "device_code": "do_am_a1",
                    "device_type": "humidity",
                    "category": "sensor",
                    "room_id": 2,
                    "metadata": {"unit": "%"}
                },
                "actuator": {
                    "device_name": "Den phong khach",
                    "device_code": "light_l1",
                    "device_type": "switch",
                    "category": "light",
                    "room_id": 1,
                    "metadata": {"brand": "ESP32 relay"}
                }
            },
            "mqtt_topic_templates": {
                "sensor_ingest": "home/sensors/{device_code}",
                "status_ingest": "home/status/{device_code}",
                "command_publish": "home/control/{device_code}"
            },
            "rest_templates": {
                "create_device": "POST /api/devices",
                "list_devices": "GET /api/devices",
                "control": "POST /api/devices/control",
                "history": "GET /api/devices/{device_code}/history",
                "sensor_detail_v2": "GET /api/devices/sensors/{device_type}/{device_code}",
                "sensor_history_v2": "GET /api/devices/sensors/{device_type}/{device_code}/history",
                "actuator_detail_v2": "GET /api/devices/actuators/{device_type}/{device_code}",
                "actuator_control_v2": "POST /api/devices/actuators/{device_type}/{device_code}/control"
            }
        }
    }), 200


# ==========================================================
# 3.6️⃣ REST V2 MIRROR
# ==========================================================
@device_api.route("/<string:category_group>/<string:device_type>/<string:device_code>", methods=["GET"], strict_slashes=False)
@auth_required
@limiter.limit("2000 per hour; 60 per minute")
def device_detail_v2(category_group: str, device_type: str, device_code: str):
    usecase: DeviceUseCase = container.device_usecase()
    snapshot = usecase.get_device_snapshot(
        device_code=device_code,
        user_id=g.current_user.id,
        category_group=category_group,
        device_type=device_type,
    )
    if not snapshot:
        return jsonify({"success": False, "message": "Device not found"}), 404
    return jsonify({"success": True, "data": snapshot}), 200


@device_api.route("/<string:category_group>/<string:device_type>/<string:device_code>/history", methods=["GET"], strict_slashes=False)
@auth_required
@limiter.limit("2000 per hour; 60 per minute")
def device_history_v2(category_group: str, device_type: str, device_code: str):
    usecase: DeviceUseCase = container.device_usecase()
    device = usecase.get_device(device_code, user_id=g.current_user.id)
    snapshot = usecase.get_device_snapshot(
        device_code=device_code,
        user_id=g.current_user.id,
        category_group=category_group,
        device_type=device_type,
    )
    if not device or not snapshot:
        return jsonify({"success": False, "message": "Device not found"}), 404

    limit = min(int(request.args.get("limit", 20)), 100)
    if str(category_group).strip().lower() in {"sensor", "sensors"}:
        readings = container.sensor_repository().get_recent_by_device_id(device.id, limit=limit)
        data = [
            {
                "id": reading.id,
                "device_id": reading.device_id,
                "device_code": device.code,
                "value": reading.value,
                "created_at": reading.created_at.isoformat() if reading.created_at else None,
            }
            for reading in readings
        ]
    else:
        logs = container.log_repository().get_by_device_id(device.id, limit=limit)
        data = [
            {
                "id": log.id,
                "device_code": log.device_code,
                "device_id": log.device_id,
                "action": log.action,
                "source": log.source,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    return jsonify({"success": True, "data": data}), 200


@device_api.route("/actuators/<string:device_type>/<string:device_code>/control", methods=["POST"], strict_slashes=False)
@auth_required
@limiter.limit("120 per minute")
def control_device_v2(device_type: str, device_code: str):
    usecase: DeviceUseCase = container.device_usecase()
    snapshot = usecase.get_device_snapshot(
        device_code=device_code,
        user_id=g.current_user.id,
        category_group="actuators",
        device_type=device_type,
    )
    if not snapshot:
        return jsonify({"success": False, "message": "Device not found"}), 404

    data = request.get_json(silent=True) or {}
    action = str(data.get("action") or data.get("value") or "").strip()
    if not action:
        return jsonify({"success": False, "message": "action or value is required"}), 400

    payload = dict(data)
    payload["device_code"] = device_code
    payload.setdefault("device_type", device_type)
    result = usecase.control_device(payload, user_id=g.current_user.id)
    return _format_response(result)


# ==========================================================
# 4️⃣ UPDATE POSITION
# ⚠ MUST BE BEFORE /<name>
# ==========================================================
@device_api.route("/update-position", methods=["POST", "OPTIONS"], strict_slashes=False)
@auth_required
def update_position():

    data = request.get_json(silent=True) or {}
    usecase: DeviceUseCase = container.device_usecase()
    result = usecase.update_device_coords(data, user_id=g.current_user.id)

    if result.get("success"):
        container.realtime_notifier().notify_device_list_changed(user_id=g.current_user.id)

    return _format_response(result)


# ==========================================================
# 5️⃣ DELETE
# ⚠ MUST BE LAST
# ==========================================================
@device_api.route("/<string:code>", methods=["DELETE", "OPTIONS"], strict_slashes=False)
@auth_required
def delete_device(code: str):

    usecase: DeviceUseCase = container.device_usecase()
    result = usecase.delete_device(code, user_id=g.current_user.id)

    if result.get("success"):
        try:
            container.realtime_notifier().notify_device_list_changed(user_id=g.current_user.id)
        except Exception as exc:
            logger.warning("DELETE succeeded but device list notify failed: %s", exc, exc_info=True)

    return _format_response(result)


# ==========================================================
# DEVICE CONTROL HISTORY
# ==========================================================
@device_api.route("/<string:device_code>/history", methods=["GET"], strict_slashes=False)
@auth_required
def device_history(device_code):
    """Return recent control logs for a specific device."""
    limit = min(int(request.args.get("limit", 20)), 100)
    device = container.device_repository().get_by_code(device_code, user_id=g.current_user.id)
    if not device:
        return jsonify({"success": False, "message": "Device not found"}), 404

    logs = container.log_repository().get_by_device_id(device.id, limit=limit)
    data = [
        {
            "id": log.id,
            "device_code": log.device_code,
            "device_id": log.device_id,
            "action": log.action,
            "source": log.source,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
    return jsonify({"success": True, "data": data}), 200