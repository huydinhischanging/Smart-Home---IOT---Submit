# app/usecases/room_usecase.py
import logging
from app.extensions.database import db
from app.infrastructure.persistence.repositories.room_repository import RoomRepository

logger = logging.getLogger(__name__)


class RoomUseCase:

    def __init__(self, room_repo: RoomRepository):
        self.room_repo = room_repo

    def create_room(self, data, user_id=None):
        try:
            name = (data.get("name") or "").strip()
            if not name:
                return {"success": False, "message": "Room name is required"}

            points       = data.get("points") or []
            polygon_data = points if isinstance(points, list) else []
            color        = data.get("color") or "rgba(253,185,19,0.22)"

            existing = self.room_repo.find_by_name_and_user(name, user_id)
            if existing:
                if color and existing.color != color:
                    self.room_repo.set_color(existing, color)
                    db.session.commit()
                logger.debug("Room '%s' already exists (id=%s)", name, existing.id)
                return {"success": True, "room_id": existing.id, "existed": True}

            room = self.room_repo.create(name, polygon_data, color, user_id)
            db.session.commit()
            logger.info("[DB] Room '%s' created id=%s color=%s", name, room.id, color)
            return {"success": True, "room_id": room.id}

        except Exception as e:
            db.session.rollback()
            logger.error("[DB] create_room error: %s", e)
            return {"success": False, "message": str(e)}

    def update_room_color(self, room_id: int, color: str):
        try:
            room = self.room_repo.find_by_id(room_id)
            if not room:
                return {"success": False, "message": "Room not found"}
            self.room_repo.set_color(room, color)
            db.session.commit()
            return {"success": True}
        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": str(e)}

    def get_all_rooms(self, user_id=None):
        try:
            rooms = self.room_repo.find_all(user_id)
            result = []
            for r in rooms:
                try:
                    device_count = len(r.devices) if r.devices else 0
                except Exception:
                    device_count = 0
                result.append({
                    "id":           r.id,
                    "name":         r.name,
                    "color":        r.color or "rgba(253,185,19,0.22)",
                    "points":       r.polygon_json,
                    "device_count": device_count,
                })
            return result
        except Exception as e:
            logger.error("[DB] get_all_rooms error: %s", e)
            return []

    def delete_room(self, room_id: int, user_id=None):
        try:
            room = self.room_repo.find_by_id(room_id, user_id)
            if not room:
                return {"success": False, "message": "Room not found"}
            name = room.name
            self.room_repo.delete(room)
            db.session.commit()
            logger.info("[DB] Room '%s' (id=%s) deleted", name, room_id)
            return {"success": True}
        except Exception as e:
            db.session.rollback()
            logger.error("[DB] delete_room error: %s", e)
            return {"success": False, "message": str(e)}
