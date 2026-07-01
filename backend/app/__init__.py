# app/__init__.py
import os
from flask import Flask, request
from flask_cors import CORS
import logging

logger = logging.getLogger(__name__)

from app.config.settings import load_flask_config
from app.wiring import load_broker_config

from app.extensions.database import db
from app.extensions.mqtt import mqtt, init_mqtt
from app.extensions.socketio import socketio
from app.extensions.auth import login_manager
from app.extensions.limiter import limiter
from app.extensions.migrate import migrate

from flask_socketio import join_room as _sio_join_room
from app.gateways.mqtt_listener import init_mqtt_listener

# ==========================================================
# IMPORT BLUEPRINTS
# ==========================================================
from app.presentation.api.device_api import device_api
from app.presentation.api.room_api import room_api
from app.presentation.api.ai_api import ai_bp
from app.presentation.api.map_api import map_bp
from app.presentation.api.coospo_api import coospo_bp
from app.presentation.api.auth_api import auth_api
from app.presentation.api.alert_api import alert_api
from app.presentation.api.reminder_api import reminder_api
from app.presentation.api.patient_report_api import patient_report_api
from app.presentation.api.automation_api import automation_api
from app.presentation.api.docs_api import docs_api
from app.presentation.api.admin_api import admin_api
from app.presentation.main.main_controller import main_controller


def create_app() -> Flask:
    app = Flask(__name__)

    # ==========================================================
    # LOAD CONFIGURATION
    # ==========================================================
    app.config.update(load_flask_config())
    app.config.update(load_broker_config())

    # ==========================================================
    # INIT EXTENSIONS
    # ==========================================================
    db.init_app(app)
    migrate.init_app(app, db)
    if app.config.get("MQTT_ENABLED", True):
        try:
            init_mqtt(app)
        except Exception as _mqtt_err:
            logger.warning(
                "MQTT init failed (%s) — app will run without real-time broker. "
                "Start EMQX on 127.0.0.1:1883 and restart to enable MQTT.",
                _mqtt_err,
            )
            app.config["MQTT_ENABLED"] = False
    else:
        logger.info("MQTT extension initialization skipped because MQTT is disabled.")

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

    login_manager.init_app(app)
    limiter.init_app(app)

    # ==========================================================
    # ENABLE CORS
    # ==========================================================
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

    # ==========================================================
    # IMPORT MODELS
    # ==========================================================
    from app.infrastructure.persistence import models  # noqa

    # ==========================================================
    # REGISTER BLUEPRINTS
    # ==========================================================
    app.register_blueprint(device_api, url_prefix="/api/devices")
    app.register_blueprint(room_api, url_prefix="/api/rooms")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")
    app.register_blueprint(auth_api, url_prefix="/api/auth")
    app.register_blueprint(alert_api, url_prefix="/api")
    app.register_blueprint(reminder_api)
    app.register_blueprint(patient_report_api, url_prefix="/api/patient")
    app.register_blueprint(coospo_bp, url_prefix="/api")
    app.register_blueprint(automation_api)
    app.register_blueprint(map_bp)
    app.register_blueprint(docs_api)
    app.register_blueprint(admin_api)
    app.register_blueprint(main_controller)

    # ==========================================================
    # INIT GATEWAYS
    # ==========================================================
    if app.config.get("MQTT_ENABLED", True):
        try:
            init_mqtt_listener(app)
        except Exception as _listener_err:
            logger.warning("MQTT listener init failed: %s", _listener_err)
    else:
        logger.info("MQTT listener initialization skipped because MQTT is disabled.")

    # ==========================================================
    # INIT SCHEDULER (schedules + automations executor)
    # ==========================================================
    from app.scheduler import init_scheduler
    init_scheduler(app)

    # ==========================================================
    # SOCKET.IO EVENT HANDLERS
    # ==========================================================
    @socketio.on("connect")
    def _on_socket_connect(auth=None):
        """Join the user-scoped room during the Socket.IO handshake when a valid token is provided."""
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

    @socketio.on("join_room")
    def _on_join_room(data):
        """Handle explicit join_room event from mobile clients that send token post-connect."""
        from app.presentation.api.auth_api import _decode_token
        try:
            token = data.get("token") if isinstance(data, dict) else None
            if not token:
                return
            user_id = _decode_token(token)
            _sio_join_room(f"user_{user_id}")
            logger.debug("Socket.IO join_room: user_%s joined", user_id)
        except Exception as exc:
            logger.debug("Socket.IO join_room: token decode failed (%s)", exc)

    # ==========================================================
    # SECURITY HEADERS
    # ==========================================================
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

    logger.info("Flask App Initialized Successfully (Alfred AI Mode)")

    return app
