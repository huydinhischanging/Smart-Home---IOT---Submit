# app/presentation/api/room_api.py
import logging

from flask import Blueprint, request, jsonify, g
from app.wiring import container
from app.presentation.api.auth_api import auth_required

room_api = Blueprint("room_api", __name__)
logger = logging.getLogger(__name__)


@room_api.route("", methods=["GET"])
@auth_required
def get_rooms():
    user_id = g.current_user.id
    rooms = container.room_usecase().get_all_rooms(user_id=user_id)
    return jsonify({"success": True, "data": rooms}), 200


@room_api.route("", methods=["POST"])
@auth_required
def create_room():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "JSON body required"}), 400
    name = str(data.get('name') or '').strip()
    if not name:
        return jsonify({"success": False, "message": "Room name is required"}), 400
    if len(name) > 100:
        return jsonify({"success": False, "message": "Room name must not exceed 100 characters"}), 400
    user_id = g.current_user.id
    logger.info("POST /rooms — name=%r user=%s", name, user_id)
    result = container.room_usecase().create_room(data, user_id=user_id)
    status = 201 if result.get("success") else 400
    return jsonify(result), status


@room_api.route("/<int:room_id>", methods=["DELETE"])
@auth_required
def delete_room(room_id):
    user_id = g.current_user.id
    logger.info("DELETE /rooms/%s user=%s", room_id, user_id)
    result = container.room_usecase().delete_room(room_id, user_id=user_id)
    status = 200 if result.get("success") else 404
    return jsonify(result), status
