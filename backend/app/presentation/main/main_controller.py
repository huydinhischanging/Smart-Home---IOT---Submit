# app/presentation/main/main_controller.py
import os
import time

from flask import Blueprint, request, jsonify, redirect, current_app

# =====================================================
# BLUEPRINT
# =====================================================
main_controller = Blueprint("main", __name__)

# Track startup time for uptime calculation
_START_TIME = time.time()


@main_controller.route("/api/health")
def healthcheck():
    from app.extensions.database import db

    db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    db_engine = "mysql"

    db_status = "ok"
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    overall = "ok" if db_status == "ok" else "degraded"

    return jsonify({
        "status": overall,
        "service": "alfred-backend",
        "version": "2.0.0",
        "environment": os.environ.get("FLASK_ENV", "development"),
        "database": db_engine,
        "database_status": db_status,
        "mqtt_enabled": bool(current_app.config.get("MQTT_ENABLED", True)),
        "uptime_seconds": int(time.time() - _START_TIME),
    }), 200 if overall == "ok" else 503


@main_controller.route("/api/metrics")
def metrics():
    """Lightweight production metrics endpoint for monitoring dashboards."""
    from app.extensions.database import db
    from app.wiring import container

    db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    db_engine = "mysql"

    db_status = "ok"
    db_pool_info: dict = {}
    try:
        db.session.execute(db.text("SELECT 1"))
        engine = db.engine
        pool = getattr(engine, "pool", None)
        if pool is not None:
            db_pool_info = {
                "pool_size": getattr(pool, "_pool", None) and pool._pool.maxsize,
                "checked_out": getattr(pool, "checkedout", lambda: None)(),
            }
    except Exception as e:
        db_status = f"error: {e}"

    uptime = int(time.time() - _START_TIME)
    
    # Email configuration status
    notifier = container.email_notifier()
    email_status = notifier.configuration_status() if notifier else {}

    return jsonify({
        "service": "alfred-backend",
        "version": "2.0.0",
        "environment": os.environ.get("FLASK_ENV", "development"),
        "uptime_seconds": uptime,
        "uptime_human": _format_uptime(uptime),
        "database": db_engine,
        "database_status": db_status,
        "database_pool": db_pool_info,
        "mqtt_enabled": bool(current_app.config.get("MQTT_ENABLED", True)),
        "debug_mode": bool(current_app.debug),
        "email": email_status,
    }), 200


def _format_uptime(seconds: int) -> str:
    """Return human-readable uptime string."""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"


# =====================================================
# DASHBOARD
# =====================================================
@main_controller.route("/")
def dashboard():
    if request.host.startswith(("localhost", "127.0.0.1")):
        return redirect("https://localhost:5173")

    return jsonify({
        "status": "ok",
        "message": "Backend is reachable",
        "host": request.host,
        "note": "Use this server URL in the mobile app settings."
    })
