from datetime import datetime, timezone

from app.extensions.database import db


class AlertSavedViewModel(db.Model):
    __tablename__ = "alert_saved_view_configs"
    __table_args__ = (
        db.Index("idx_alert_saved_view_user", "user_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    views_json = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<AlertSavedViewModel user_id={self.user_id}>"