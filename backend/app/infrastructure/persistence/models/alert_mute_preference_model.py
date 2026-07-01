from datetime import datetime, timezone

from app.extensions.database import db


class AlertMutePreferenceModel(db.Model):
    __tablename__ = "alert_mute_preferences"
    __table_args__ = (
        db.Index("idx_alert_mute_pref_user", "user_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    mute_scope = db.Column(db.String(32), nullable=False, default="none")
    mute_keyword = db.Column(db.String(64), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<AlertMutePreferenceModel user_id={self.user_id} scope={self.mute_scope}>"
