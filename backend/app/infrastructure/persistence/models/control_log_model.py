# app/infrastructure/persistence/models/control_log_model.py
from datetime import datetime, timezone
from app.extensions.database import db


class ControlLog(db.Model):
    __tablename__ = "control_log"
    __table_args__ = (
        db.Index("idx_device_created", "device_id", "created_at"),
        db.Index("idx_source_created", "source", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)

    # Audit field: preserved even when the device is deleted (device_id becomes NULL).
    device_code = db.Column(
        db.String(50),
        nullable=True,
        index=True,
    )

    device_id = db.Column(
        db.Integer,
        db.ForeignKey("device.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action = db.Column(
        db.String(255),
        nullable=False,
    )

    source = db.Column(
        db.String(50),
        nullable=True,
        index=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # ==========================================================
    # RELATIONSHIPS
    # ==========================================================
    device = db.relationship(
        "Device",
        back_populates="logs",
        lazy="joined",
        passive_deletes=True,
    )

    def __repr__(self):
        return (
            f"<ControlLog id={self.id} "
            f"device_id={self.device_id} "
            f"action={self.action} "
            f"source={self.source}>"
        )