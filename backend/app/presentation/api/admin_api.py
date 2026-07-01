# app/presentation/api/admin_api.py
import logging
from flask import Blueprint, jsonify, g
from app.extensions.database import db
from app.infrastructure.persistence.models.user_model import UserModel
from app.presentation.api.auth_api import auth_required, admin_required

logger = logging.getLogger(__name__)

admin_api = Blueprint("admin_api", __name__, url_prefix="/api/admin")


@admin_api.route("/users", methods=["GET"])
@auth_required
@admin_required
def list_users():
    users = UserModel.query.order_by(UserModel.id).all()
    return jsonify({
        "status": "success",
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]
    })


@admin_api.route("/users/<int:user_id>", methods=["DELETE"])
@auth_required
@admin_required
def delete_user(user_id):
    if user_id == g.current_user.id:
        return jsonify({"status": "error", "message": "Cannot delete your own account"}), 400

    user = db.session.get(UserModel, user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    db.session.delete(user)
    db.session.commit()
    logger.info("Admin %s deleted user ID:%s (%s)", g.current_user.username, user_id, user.username)
    return jsonify({"status": "success", "message": f"User '{user.username}' deleted"})


@admin_api.route("/users/<int:user_id>/role", methods=["PATCH"])
@auth_required
@admin_required
def update_role(user_id):
    from flask import request
    data = request.get_json(silent=True) or {}
    new_role = data.get("role", "").strip().lower()

    if new_role not in ("user", "admin"):
        return jsonify({"status": "error", "message": "Role must be 'user' or 'admin'"}), 400

    if user_id == g.current_user.id:
        return jsonify({"status": "error", "message": "Cannot change your own role"}), 400

    user = db.session.get(UserModel, user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    user.role = new_role
    db.session.commit()
    logger.info("Admin %s set user ID:%s role -> %s", g.current_user.username, user_id, new_role)
    return jsonify({"status": "success", "user": {"id": user.id, "username": user.username, "role": user.role}})
