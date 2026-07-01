# app/infrastructure/persistence/models/rooms_model.py
from app.extensions.database import db
from datetime import datetime, timezone


class RoomModel(db.Model):

    __tablename__ = "rooms"

    __table_args__ = (
        db.Index("idx_room_name", "name"),
        db.Index("idx_room_created", "created_at"),
        db.Index("idx_room_user", "user_id"),
    )

    id = db.Column(db.Integer, primary_key=True)

    # multi-tenant owner
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )

    name = db.Column(db.String(100), nullable=False)

    polygon_data = db.Column(db.JSON, nullable=False, default=list)

    color = db.Column(
        db.String(80),
        nullable=False,
        default='rgba(253,185,19,0.22)'
    )

    floorplan_url = db.Column(db.String(255), nullable=True)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    devices = db.relationship(
        "Device",
        back_populates="room",
        passive_deletes=True,
    )

    @property
    def polygon_json(self):
        data = self.polygon_data
        return data if isinstance(data, list) else []

    @polygon_json.setter
    def polygon_json(self, value):
        self.polygon_data = value if isinstance(value, list) else []

    def __repr__(self):
        return f"<RoomModel id={self.id} name={self.name} color={self.color}>"
