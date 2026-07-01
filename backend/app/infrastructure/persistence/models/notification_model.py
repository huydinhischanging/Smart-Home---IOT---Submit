#app/infrastructure/persistence/models/user_model.py
# ==========================================================
# FILE: notification_model.py
# Smart Home – Notification Entity
# ==========================================================

from datetime import datetime, timezone
from app.extensions.database import db
from sqlalchemy.orm import relationship


class NotificationModel(db.Model):

    __tablename__ = "notifications"

    __table_args__ = (
        db.Index("idx_notif_user_read", "user_id", "is_read"),
        db.Index("idx_notif_created", "created_at"),
        db.Index("idx_notif_alert", "alert_id"),
    )

    # ==========================================================
    # PRIMARY KEY
    # ==========================================================
    id = db.Column(db.Integer, primary_key=True)

    # ==========================================================
    # FOREIGN KEY → USER
    # ==========================================================
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ==========================================================
    # FOREIGN KEY → ALERT (tuỳ chọn)
    # ==========================================================
    alert_id = db.Column(
        db.Integer,
        db.ForeignKey("alerts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ==========================================================
    # CONTENT
    # ==========================================================
    title = db.Column(
        db.String(255),
        nullable=False,
    )

    body = db.Column(
        db.Text,
        nullable=False,
    )

    is_read = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ==========================================================
    # RELATIONSHIPS
    # ==========================================================
    user = relationship(
        "UserModel",
        back_populates="notifications",
        passive_deletes=True,
    )

    alert = relationship(
        "AlertModel",
        back_populates="notifications",
        passive_deletes=True,
    )

    # ==========================================================
    # DEBUG
    # ==========================================================
    def __repr__(self):
        return (
            f"<NotificationModel id={self.id} "
            f"user_id={self.user_id} "
            f"is_read={self.is_read}>"
        )