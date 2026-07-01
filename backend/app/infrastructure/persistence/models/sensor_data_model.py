#app/infrastructure/persistence/models/sensor_data_model.py
# ==========================================================
# FILE: sensor_data_model.py
# Smart Home – Sensor Data
# ==========================================================

from datetime import datetime, timezone

from app.extensions.database import db
from sqlalchemy.orm import relationship


class SensorData(db.Model):

    __tablename__ = "sensor_data"

    __table_args__ = (
        db.Index("idx_sensor_device_time", "device_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)

    device_id = db.Column(
        db.Integer,
        db.ForeignKey("device.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    value = db.Column(
        db.Float,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    device = relationship(
        "Device",
        back_populates="sensor_data",
        passive_deletes=True,
    )

    def __repr__(self):
        return (
            f"<SensorData id={self.id} "
            f"device_id={self.device_id} "
            f"value={self.value}>"
        )