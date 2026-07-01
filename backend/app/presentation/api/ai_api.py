# app/presentation/api/ai_api.py

import logging
from flask import Blueprint, request, jsonify, g
from app.wiring import container
from app.presentation.api.auth_api import auth_required
from app.extensions.limiter import limiter
from app.infrastructure.persistence.repositories.patient_profile_repository import PatientProfileRepository

logger = logging.getLogger(__name__)


# ==========================================================
# Blueprint
# ==========================================================
ai_bp = Blueprint(
    "ai",
    __name__,
    url_prefix="/api/ai"
)


# ==========================================================
# 🔎 AI STATUS
# ==========================================================
@ai_bp.route("/status", methods=["GET"])
@auth_required
def get_ai_status():
    """
    Check Alfred AI status
    """

    return jsonify({
        "engine": "Alfred AI",
        "version": "2.0",
        "status": "online",
        "modules": [
            "chat",
            "device_control",
            "sensor_analysis",
            "automation"
        ]
    })


# ==========================================================
# 💬 AI CHAT
# ==========================================================
@ai_bp.route("/chat", methods=["POST"])
@auth_required
@limiter.limit("30 per minute; 300 per hour")
def chat():
    """
    Chat with Alfred AI
    """

    data = request.get_json()

    # ------------------------------------------
    # Validate JSON body
    # ------------------------------------------
    if not data:
        return jsonify({
            "status": "error",
            "message": "JSON body required"
        }), 400

    message = data.get("message")
    mode = data.get("mode", "llm")  # optional: rule, llm, gemini
    language = data.get("language", "vi")
    context_data = data.get("context")  # optional

    if not message:
        return jsonify({
            "status": "error",
            "message": "Message is required"
        }), 400

    try:

        logger.debug("AI API received: %s (mode=%s)", message, mode)

        # --------------------------------------
        # Resolve AIUseCase from container
        # --------------------------------------
        ai_usecase = container.ai_usecase()

        # --------------------------------------
        # Resolve display name: patient_name > username
        # --------------------------------------
        _display_name = PatientProfileRepository().get_display_name(
            g.current_user.id, fallback=g.current_user.username
        )

        # --------------------------------------
        # Call AI UseCase with user_id
        # --------------------------------------
        result = ai_usecase.handle_chat(
            message=message,
            context_data=context_data,
            mode=mode,
            language=language,
            user_id=g.current_user.id,
            username=_display_name,
        )

        # --------------------------------------
        # Response
        # --------------------------------------
        if isinstance(result, dict):
            response = {"status": "success", "mode": mode, **result}
        else:
            response = {"status": "success", "mode": mode, "reply": str(result)}

        return jsonify(response)

    except Exception as e:
        logger.error("AI API error: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ==========================================================
# 🧠 AI PROCESS SENSOR DATA (OPTIONAL)
# ==========================================================
@ai_bp.route("/analyze", methods=["POST"])
@auth_required
@limiter.limit("60 per minute")
def analyze_sensors():
    """
    Send sensor data to AI for analysis
    """

    data = request.get_json()

    if not data:
        return jsonify({
            "status": "error",
            "message": "JSON body required"
        }), 400

    try:

        ai_usecase = container.ai_usecase()

        results = ai_usecase.process_sensors(data)

        return jsonify({
            "status": "success",
            "analysis": results
        })

    except Exception as e:
        logger.error("Sensor AI error: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500