# ==========================================================
# FILE: alert_rule_model.py
# Smart Home – Alert Rule (FINAL PRODUCTION VERSION)
# ==========================================================

from datetime import datetime, timezone
from app.extensions.database import db
from sqlalchemy.orm import relationship


class AlertRuleModel(db.Model):

    __tablename__ = "alert_rules"

    __table_args__ = (
        db.Index(
            "idx_rule_device_sensor_active",
            "device_id",
            "sensor_type",
            "is_active"
        ),
        db.Index("idx_rule_created", "created_at"),
        db.Index("idx_rule_user", "user_id"),
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
        nullable=False,
        index=True,
    )

    # ==========================================================
    # RULE CONFIG
    # ==========================================================
    sensor_type = db.Column(
        db.String(50),
        nullable=False,
        index=True,
    )

    min_value = db.Column(
        db.Float,
        nullable=True,
    )

    max_value = db.Column(
        db.Float,
        nullable=True,
    )

    # ==========================================================
    # STATUS
    # ==========================================================
    is_active = db.Column(
        db.Boolean,
        default=True,
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
    # RELATIONSHIP (SYNC WITH DEVICE)
    # ==========================================================
    device = relationship(
        "Device",
        back_populates="alert_rules",
        passive_deletes=True,
    )

    # ==========================================================
    # DEBUG
    # ==========================================================
    def __repr__(self):
        return (
            f"<AlertRuleModel id={self.id} "
            f"device_id={self.device_id} "
            f"sensor={self.sensor_type} "
            f"min={self.min_value} "
            f"max={self.max_value} "
            f"active={self.is_active}>"
        )