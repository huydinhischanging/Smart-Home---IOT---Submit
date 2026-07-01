# app/presentation/api/coospo_api.py
# ============================================================
# Coospo H6 BLE Heart Rate — REST API
# Quản lý kết nối/ngắt kết nối và trạng thái real-time
# ============================================================
import logging
import subprocess
import sys
import os
import threading
import time
from flask import Blueprint, jsonify, request
from app.presentation.api.auth_api import auth_required
from app.extensions.limiter import limiter

logger = logging.getLogger(__name__)

coospo_bp = Blueprint("coospo", __name__)

# ── State (in-memory) ──
_state = {
    "connected":   False,
    "bpm":         0,
    "device_name": None,
    "room_temp":   None,
    "humidity":    None,
    "light_level": None,
    "process":     None,   # subprocess handle
    "last_update": None,   # None = never received; 0 is falsy and breaks stale check
}
_hr_alerts = []  # list of last broadcasted HR alerts
_lock = threading.Lock()

# Max number of HR alerts to keep in memory
_HR_ALERTS_MAX = 100
_STALE_TIMEOUT_SEC = 20
_ENABLE_DEBUG_ALERT = os.getenv("ENABLE_DEBUG_ALERT", "0").strip().lower() in {"1", "true", "yes", "on"}


def update_state(**kwargs):
    with _lock:
        _state.update(kwargs)


def get_state() -> dict:
    with _lock:
        return dict(_state)


# ─────────────────────────────────────────
# MQTT listener để nhận BPM từ coospo_reader.py
# coospo_reader.py publish → EMQX → mqtt_listener → socket
# → Frontend gọi /api/coospo/status để poll
# ─────────────────────────────────────────
def on_heart_rate_received(bpm: int,
                           device_name: str = "Coospo H6",
                           room_temp: float | None = None,
                           humidity: float | None = None,
                           light_level: float | None = None):
    """Gọi từ mqtt_listener khi nhận home/sensors/heart_rate."""
    update_state(
        connected=True,
        bpm=bpm,
        device_name=device_name,
        room_temp=room_temp,
        humidity=humidity,
        light_level=light_level,
        last_update=time.time()
    )


def add_hr_alert(alert: dict):
    """Lưu alert history để frontend query qua REST"""
    global _hr_alerts
    _hr_alerts.append(alert)
    if len(_hr_alerts) > _HR_ALERTS_MAX:
        _hr_alerts = _hr_alerts[-_HR_ALERTS_MAX:]


@coospo_bp.route("/coospo/hr_alert", methods=["GET"])
@auth_required
def hr_alert():
    """Trả về lịch sử HR alert (mới nhất trước)."""
    state = get_state()
    safe_state = {k: v for k, v in state.items() if k != "process"}
    return jsonify({
        "status": "ok",
        "state": safe_state,
        "hr_alerts": list(reversed(_hr_alerts[-20:])),
    })


# ─────────────────────────────────────────
# API Routes
# ─────────────────────────────────────────
@coospo_bp.route("/coospo/connect", methods=["POST"])
@auth_required
def connect():
    """Khởi động coospo_reader.py subprocess."""
    state = get_state()
    if state["process"] and state["process"].poll() is None:
        return jsonify({"success": True, "message": "Already running", "device_name": state["device_name"]})

    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        script   = os.path.join(base_dir, "coospo_reader.py")

        # Fallback: tìm từ thư mục hiện tại
        if not os.path.exists(script):
            script = os.path.join(os.getcwd(), "coospo_reader.py")

        if not os.path.exists(script):
            return jsonify({"success": False, "message": f"coospo_reader.py not found at {script}"}), 404

        proc = subprocess.Popen(
            [sys.executable, script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",   # Fix: Windows cp1252 can't decode UTF-8 emoji
            errors="replace",   # Replace undecodable chars instead of crashing
            bufsize=1,
        )
        update_state(process=proc, connected=False, bpm=0)

        # Thread đọc output để log
        def _read_output():
            for line in proc.stdout:
                line = line.strip()
                if line:
                    logger.info("[Coospo] %s", line)
                    # Detect connected status từ stdout
                    if "Connected!" in line or "Streaming" in line:
                        # Update last_update so stale check passes immediately;
                        # MQTT data will refresh it further once BPM arrives.
                        update_state(connected=True, last_update=time.time())
                    elif "Coospo H6 found" in line or "found by name" in line or "Heart Rate device found" in line:
                        # Extract device name from: "✅ Coospo H6 found by name: DevName [MAC]"
                        # or "✅ Heart Rate device found: DevName [MAC]"
                        try:
                            name = line.split("name:")[1].strip().split("[")[0].strip()
                            update_state(device_name=name)
                        except Exception:
                            pass
                    elif "BLE disconnected" in line:
                        logger.warning("[Coospo] BLE disconnected — waiting for reconnect")
                        update_state(connected=False)
                    elif "Max retries" in line or "Giving up" in line:
                        update_state(connected=False, last_update=None)
            update_state(connected=False, process=None, last_update=None)

        threading.Thread(target=_read_output, daemon=True).start()

        return jsonify({"success": True, "message": "Coospo reader started — scanning BLE..."})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@coospo_bp.route("/coospo/disconnect", methods=["POST"])
@auth_required
def disconnect():
    """Dừng coospo_reader.py."""
    state = get_state()
    proc = state.get("process")
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

    update_state(connected=False, bpm=0, device_name=None, process=None)
    return jsonify({"success": True, "message": "Disconnected"})


@coospo_bp.route("/coospo/status", methods=["GET"])
@limiter.limit("720 per hour")
@auth_required
def status():
    """Trả về trạng thái kết nối và BPM hiện tại."""
    state = get_state()
    proc  = state.get("process")

    # Check process còn chạy không
    proc_alive = proc is not None and proc.poll() is None

    # Nếu không nhận BPM quá lâu thì mới coi là stale (tránh nháy disconnect khi mạng chập chờn)
    # Use explicit None check — 0 is falsy but is a valid timestamp edge case
    stale_sec = (time.time() - state["last_update"]) if state["last_update"] is not None else float("inf")
    stale = stale_sec > _STALE_TIMEOUT_SEC
    connected = proc_alive and state["connected"] and not stale

    return jsonify({
        "connected":   connected,
        "bpm":         state["bpm"],
        "device_name": state["device_name"],
        "proc_alive":  proc_alive,
        "stale":       stale,
        "stale_sec":   round(stale_sec, 2) if stale_sec != float("inf") else None,
        "timeout_sec": _STALE_TIMEOUT_SEC,
    })


@coospo_bp.route("/coospo/debug_alert", methods=["POST"])
@auth_required
def debug_alert():
    """Debug endpoint: emit a synthetic HR alert to frontend without MQTT."""
    if not _ENABLE_DEBUG_ALERT:
        return jsonify({
            "success": False,
            "message": "debug_alert is disabled. Set ENABLE_DEBUG_ALERT=1 to enable.",
        }), 404

    data = request.get_json(silent=True) or {}
    bpm = int(data.get("bpm", 155))
    risk = str(data.get("risk", "emergency"))
    severity = str(data.get("severity", "critical"))
    mood = str(data.get("mood", "ACTIVE"))

    payload = {
        "bpm": bpm,
        "risk": risk,
        "severity": severity,
        "is_anomaly": bool(data.get("is_anomaly", False)),
        "mood": mood,
        "timestamp": time.strftime("%H:%M:%S"),
        "message": data.get("message", f"Heart Rate {bpm} BPM ({risk})"),
    }

    client_count = None
    try:
        from app.extensions.socketio import socketio

        # Count unique connected sids in default namespace for quick diagnostics.
        try:
            rooms = socketio.server.manager.rooms.get("/", {})
            connected_sids = set()
            for participants in rooms.values():
                connected_sids.update(participants)
            client_count = len(connected_sids)
        except Exception:
            client_count = None

        socketio.emit("hr_alert", payload)
        socketio.emit("alert", {
            "device_code": "heart_rate",
            "level": severity.upper(),
            "message": payload["message"],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"socket emit failed: {e}"}), 500

    add_hr_alert(payload)
    return jsonify({
        "success": True,
        "payload": payload,
        "socket_clients": client_count,
    })
