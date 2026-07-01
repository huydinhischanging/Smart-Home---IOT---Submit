# app/infrastructure/persistence/models/user_model.py
from datetime import datetime, timezone
from app.extensions.database import db
from sqlalchemy.orm import relationship


class UserModel(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.Index("idx_user_email", "email"),
        db.Index("idx_user_role", "role"),
        db.Index("idx_user_active", "is_active"),
    )

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), nullable=False, unique=True)
    email    = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)

    role = db.Column(
        db.Enum("admin", "user", "guest"),
        nullable=False,
        default="user",
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # ==========================================================
    # RELATIONSHIPS
    # ==========================================================
    notifications = relationship(
        "NotificationModel",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    schedules = relationship(
        "ScheduleModel",
        back_populates="creator",
        foreign_keys="ScheduleModel.created_by",
        passive_deletes=True,
    )

    # ✅ FIX: Bỏ control_logs — ControlLog không còn user_id
    # control_logs = relationship("ControlLog", back_populates="user", ...)

    def __repr__(self):
        return f"<UserModel id={self.id} username={self.username} role={self.role}>"