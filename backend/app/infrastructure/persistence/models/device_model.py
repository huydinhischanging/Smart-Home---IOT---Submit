#app/infrastructure/persistence/models/device_model.py
# ==========================================================
# FILE: device_model.py
# Smart Home – Device Entity (FINAL FULLY SYNCHRONIZED VERSION)
# ==========================================================

from datetime import datetime, timezone
from app.extensions.database import db
from sqlalchemy.orm import relationship


class Device(db.Model):

    __tablename__ = "device"

    __table_args__ = (
        # Per-user unique code: two different users can have "den", "quat", etc.
        db.UniqueConstraint("code", "user_id", name="uq_device_code_user"),
        db.Index("idx_device_code", "code"),
        db.Index("idx_device_category", "category"),
        db.Index("idx_device_room", "room_id"),
        db.Index("idx_device_deleted", "is_deleted"),
        db.Index("idx_device_user", "user_id"),
    )

    # ==========================================================
    # PRIMARY KEY
    # ==========================================================
    id = db.Column(db.Integer, primary_key=True)

    # ==========================================================
    # OWNER (multi-tenant)
    # ==========================================================
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )

    # ==========================================================
    # BASIC INFO
    # ==========================================================
    name = db.Column(db.String(100), nullable=False)

    code = db.Column(
        db.String(50),
        nullable=False,
    )

    icon = db.Column(
        db.String(50),
        nullable=False,
        default="💡",
    )

    control_types = db.Column(
        db.JSON,
        nullable=False,
        default=list,
    )

    device_type = db.Column(
        db.String(50),
        nullable=True,
    )

    metadata_json = db.Column(
        db.JSON,
        nullable=False,
        default=dict,
    )

    # ==========================================================
    # DEVICE CLASSIFICATION
    # ==========================================================
    category = db.Column(
        db.Enum("sensor", "actuator", "light", "fan", "ac", "camera", "lock", "switch", "tv", "speaker", "other"),
        nullable=False,
        default="sensor",
    )

    # ==========================================================
    # ROOM MAPPING
    # ==========================================================
    room_id = db.Column(
        db.Integer,
        db.ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
    )

    map_x = db.Column(db.Float, nullable=True)
    map_y = db.Column(db.Float, nullable=True)

    # ==========================================================
    # SOFT DELETE
    # ==========================================================
    is_deleted = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    deleted_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    # ==========================================================
    # RELATIONSHIPS (FULLY MATCHED WITH FK RULES)
    # ==========================================================

    # FK: NO ACTION
    status = relationship(
        "DeviceStatus",
        back_populates="device",
        uselist=False,
        passive_deletes=True,
    )

    # FK: ON DELETE SET NULL
    logs = relationship(
        "ControlLog",
        back_populates="device",
        passive_deletes=True,
    )

    # FK: ON DELETE CASCADE
    sensor_data = relationship(
        "SensorData",
        back_populates="device",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # FK: ON DELETE CASCADE
    alerts = relationship(
        "AlertModel",
        back_populates="device",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # FK: ON DELETE CASCADE
    alert_rules = relationship(
        "AlertRuleModel",
        back_populates="device",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # FK: ON DELETE SET NULL
    room = relationship(
        "RoomModel",
        back_populates="devices",
        passive_deletes=True,
    )

    # FK: ON DELETE CASCADE
    schedules = relationship(
        "ScheduleModel",
        back_populates="device",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # FK: ON DELETE CASCADE (trigger)
    automations_as_trigger = relationship(
        "AutomationModel",
        foreign_keys="AutomationModel.trigger_device_id",
        back_populates="trigger_device",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # FK: ON DELETE CASCADE (action)
    automations_as_action = relationship(
        "AutomationModel",
        foreign_keys="AutomationModel.action_device_id",
        back_populates="action_device",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # ==========================================================
    # JSON HELPER
    # ==========================================================

    @property
    def types_list(self):
        data = self.control_types
        return data if isinstance(data, list) else []

    @types_list.setter
    def types_list(self, value):
        self.control_types = value if isinstance(value, list) else []

    @property
    def metadata_dict(self):
        data = self.metadata_json
        return data if isinstance(data, dict) else {}

    @metadata_dict.setter
    def metadata_dict(self, value):
        self.metadata_json = value if isinstance(value, dict) else {}

    # ==========================================================
    # SOFT DELETE METHODS
    # ==========================================================

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None

    # ==========================================================
    # DEBUG
    # ==========================================================

    def __repr__(self):
        return (
            f"<Device id={self.id} "
            f"name={self.name} "
            f"code={self.code} "
            f"device_type={self.device_type} "
            f"category={self.category} "
            f"room_id={self.room_id} "
            f"is_deleted={self.is_deleted}>"
        )