from app.extensions.database import db
from sqlalchemy.orm import relationship
from datetime import datetime, timezone


class DeviceStatus(db.Model):

    __tablename__ = "device_status"

    id = db.Column(db.Integer, primary_key=True)

    is_on = db.Column(db.Boolean, nullable=True)

    value = db.Column(db.String(50), nullable=True)

    updated_at = db.Column(
        db.DateTime,
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    device_id = db.Column(
        db.Integer,
        db.ForeignKey("device.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    device = relationship(
        "Device",
        back_populates="status",
        passive_deletes=True,
    )

    def __repr__(self):
        return (
            f"<DeviceStatus device_id={self.device_id} "
            f"is_on={self.is_on} "
            f"value={self.value}>"
        )