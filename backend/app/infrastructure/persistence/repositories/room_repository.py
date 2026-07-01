# app/infrastructure/persistence/repositories/room_repository.py
from typing import Optional, List
from app.extensions.database import db
from app.infrastructure.persistence.models.rooms_model import RoomModel


class RoomRepository:

    def find_by_name_and_user(self, name: str, user_id) -> Optional[RoomModel]:
        return RoomModel.query.filter_by(name=name, user_id=user_id).first()

    def find_all(self, user_id=None) -> List[RoomModel]:
        q = RoomModel.query
        if user_id is not None:
            q = q.filter_by(user_id=user_id)
        return q.all()

    def find_by_id(self, room_id: int, user_id=None) -> Optional[RoomModel]:
        q = RoomModel.query.filter_by(id=room_id)
        if user_id is not None:
            q = q.filter_by(user_id=user_id)
        return q.first()

    def create(self, name: str, polygon_data: list, color: str, user_id) -> RoomModel:
        room = RoomModel(name=name, polygon_data=polygon_data, color=color, user_id=user_id)
        db.session.add(room)
        db.session.flush()
        return room

    def set_color(self, room: RoomModel, color: str) -> None:
        room.color = color
        db.session.flush()

    def delete(self, room: RoomModel) -> None:
        db.session.delete(room)
        db.session.flush()
