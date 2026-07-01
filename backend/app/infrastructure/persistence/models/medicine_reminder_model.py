from datetime import date, datetime, timezone

from app.extensions.database import db
from sqlalchemy.orm import relationship


class MedicineReminderModel(db.Model):
    __tablename__ = "medicine_reminders"

    __table_args__ = (
        db.Index("idx_med_reminder_user", "user_id"),
        db.Index("idx_med_reminder_time", "is_active", "time_of_day"),
    )

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    medicine_name = db.Column(db.String(60), nullable=False)
    dosage = db.Column(db.String(80), nullable=False)
    time_of_day = db.Column(db.String(5), nullable=False)
    recurrence = db.Column(
        db.Enum("daily", "weekday", "weekend"),
        nullable=False,
        default="daily",
    )
    notify_email = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_sent_on = db.Column(db.Date, nullable=True)
    last_taken_on = db.Column(db.Date, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("UserModel", passive_deletes=True)

    @property
    def taken_today(self) -> bool:
        return self.last_taken_on == date.today()

    def __repr__(self):
        return (
            f"<MedicineReminderModel id={self.id} user_id={self.user_id} "
            f"time_of_day={self.time_of_day} recurrence={self.recurrence}>"
        )