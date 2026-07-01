#
# ==========================================================
# FILE: automation_model.py
# Smart Home – Automation Entity (if X then do Y)
# ==========================================================

import re
from datetime import datetime, timezone
from app.extensions.database import db
from sqlalchemy.orm import relationship, validates

# Allowed format: "value > 35" | "is_on == true" — evaluated via regex in scheduler, never via eval()
_CONDITION_RE = re.compile(r'^(value|is_on)\s*(==|!=|>=|<=|>|<)\s*.+$', re.IGNORECASE)


class AutomationModel(db.Model):

    __tablename__ = "automations"

    __table_args__ = (
        db.Index("idx_automation_trigger", "trigger_device_id"),
        db.Index("idx_automation_action", "action_device_id"),
        db.Index("idx_automation_active", "is_active"),
    )

    # ==========================================================
    # PRIMARY KEY
    # ==========================================================
    id = db.Column(db.Integer, primary_key=True)

    # ==========================================================
    # NAME
    # ==========================================================
    name = db.Column(
        db.String(100),
        nullable=False,
    )

    # ==========================================================
    # TRIGGER — device that activates the automation
    # ==========================================================
    trigger_device_id = db.Column(
        db.Integer,
        db.ForeignKey("device.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Format: "value > 35" or "is_on == true". Validated on write; evaluated via regex in scheduler.
    trigger_condition = db.Column(
        db.String(255),
        nullable=False,
    )

    # ==========================================================
    # ACTION — target device
    # ==========================================================
    action_device_id = db.Column(
        db.Integer,
        db.ForeignKey("device.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Stored as JSON. Example: {"is_on": true} or {"value": "25"}
    action_payload = db.Column(
        db.JSON,
        nullable=False,
    )

    # ==========================================================
    # STATUS
    # ==========================================================
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ==========================================================
    # RELATIONSHIPS
    # ==========================================================
    trigger_device = relationship(
        "Device",
        foreign_keys=[trigger_device_id],
        back_populates="automations_as_trigger",
        passive_deletes=True,
    )

    action_device = relationship(
        "Device",
        foreign_keys=[action_device_id],
        back_populates="automations_as_action",
        passive_deletes=True,
    )

    @validates('trigger_condition')
    def validate_trigger_condition(self, key, value):
        v = (value or '').strip()
        if not _CONDITION_RE.match(v):
            raise ValueError(
                f"Invalid trigger_condition '{v}'. "
                "Expected format: 'value > 35' or 'is_on == true'."
            )
        return v

    # ==========================================================
    # DEBUG
    # ==========================================================
    def __repr__(self):
        return (
            f"<AutomationModel id={self.id} "
            f"name={self.name} "
            f"trigger_device_id={self.trigger_device_id} "
            f"action_device_id={self.action_device_id} "
            f"is_active={self.is_active}>"
        )