#app/infrastructure/persistence/models/alert_model.py
# ==========================================================
# FILE: alert_model.py
# Smart Home – Alert (FINAL PRODUCTION VERSION)
# ==========================================================
from datetime import datetime, timezone
from app.extensions.database import db
from sqlalchemy.orm import relationship


class AlertModel(db.Model):

    __tablename__ = "alerts"

    __table_args__ = (
        db.Index("idx_alert_device", "device_id"),
        db.Index("idx_alert_read_time", "is_read", "created_at"),
        db.Index("idx_alert_created", "created_at"),
        db.Index("idx_alert_user", "user_id"),
    )

    # ==========================================================
    # PRIMARY KEY
    # ==========================================================
    id = db.Column(db.Integer, primary_key=True)

    # ==========================================================
    # OWNER (multi-tenant) — nullable for backward compat
    # ==========================================================
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # ==========================================================
    # FOREIGN KEY → DEVICE
    # ==========================================================
    device_id = db.Column(
        db.Integer,
        db.ForeignKey("device.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # ==========================================================
    # ALERT CONTENT
    # ==========================================================
    # Audit field: preserved even when the device is deleted (device_id becomes NULL).
    device_code = db.Column(
        db.String(50),
        nullable=False,
    )

    message = db.Column(
        db.String(255),
        nullable=False,
    )

    level = db.Column(
        db.Enum("info", "warning", "critical"),
        nullable=False,
        default="warning",
    )

    # ==========================================================
    # READ STATUS
    # ==========================================================
    is_read = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    # ==========================================================
    # CREATED TIME
    # ==========================================================
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # ==========================================================
    # RELATIONSHIPS
    # ==========================================================
    device = relationship(
        "Device",
        back_populates="alerts",
        passive_deletes=True,
    )

    notifications = relationship(
        "NotificationModel",
        back_populates="alert",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # ==========================================================
    # DEBUG
    # ==========================================================
    def __repr__(self):
        return (
            f"<AlertModel id={self.id} "
            f"device_id={self.device_id} "
            f"level={self.level} "
            f"is_read={self.is_read}>"
        )