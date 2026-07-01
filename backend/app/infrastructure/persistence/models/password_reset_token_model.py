from datetime import datetime, timezone

from app.extensions.database import db


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PasswordResetTokenModel(db.Model):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        db.Index("idx_password_reset_token_user", "user_id"),
        db.Index("idx_password_reset_token_expiry", "expires_at"),
        db.Index("idx_password_reset_token_used", "used_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow_naive)

    def __repr__(self):
        return (
            f"<PasswordResetTokenModel id={self.id} user_id={self.user_id} "
            f"used={self.used_at is not None}>"
        )