#app/infrastructure/persistence/models/schedule_model.py
# ==========================================================
# FILE: schedule_model.py
# Smart Home – Schedule Entity (tự động bật/tắt thiết bị)
# ==========================================================

from datetime import datetime, timezone
from app.extensions.database import db
from sqlalchemy.orm import relationship


class ScheduleModel(db.Model):

    __tablename__ = "schedules"

    __table_args__ = (
        db.Index("idx_schedule_device", "device_id"),
        db.Index("idx_schedule_active", "is_active"),
        db.Index("idx_schedule_creator", "created_by"),
    )

    # ==========================================================
    # PRIMARY KEY
    # ==========================================================
    id = db.Column(db.Integer, primary_key=True)

    # ==========================================================
    # FOREIGN KEY → DEVICE
    # ==========================================================
    device_id = db.Column(
        db.Integer,
        db.ForeignKey("device.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ==========================================================
    # SCHEDULE CONFIG
    # ==========================================================
    # JSON dict. Example: {"is_on": true, "value": "25"}
    action = db.Column(
        db.JSON,
        nullable=False,
    )

    # Cron expression. Example: "0 7 * * 1-5" (7am Mon-Fri)
    cron_expr = db.Column(
        db.String(100),
        nullable=False,
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    # Human-readable label, e.g. "Sleep mode", "Morning routine"
    label = db.Column(
        db.String(100),
        nullable=True,
    )

    # If True: emit a socket reminder popup instead of auto-executing MQTT
    remind_only = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    # ==========================================================
    # FOREIGN KEY → USER (người tạo lịch)
    # ==========================================================
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ==========================================================
    # RELATIONSHIPS
    # ==========================================================
    device = relationship(
        "Device",
        back_populates="schedules",
        passive_deletes=True,
    )

    creator = relationship(
        "UserModel",
        back_populates="schedules",
        foreign_keys=[created_by],
        passive_deletes=True,
    )

    # ==========================================================
    # DEBUG
    # ==========================================================
    def __repr__(self):
        return (
            f"<ScheduleModel id={self.id} "
            f"device_id={self.device_id} "
            f"cron_expr={self.cron_expr} "
            f"is_active={self.is_active}>"
        )