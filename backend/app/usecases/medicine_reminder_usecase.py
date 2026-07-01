import logging
import re
from datetime import date, datetime, timedelta

from app.extensions.database import db
from app.infrastructure.persistence.models.medicine_reminder_model import MedicineReminderModel
from app.infrastructure.persistence.repositories.medicine_reminder_repository import MedicineReminderRepository


logger = logging.getLogger(__name__)

_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class MedicineReminderUseCase:
    def __init__(self, email_notifier, alert_usecase, reminder_repo: MedicineReminderRepository):
        self.email_notifier = email_notifier
        self.alert_usecase = alert_usecase
        self.reminder_repo = reminder_repo

    @staticmethod
    def serialize(reminder: MedicineReminderModel) -> dict:
        return {
            "id": reminder.id,
            "name": reminder.medicine_name,
            "dose": reminder.dosage,
            "time": reminder.time_of_day,
            "days": reminder.recurrence,
            "notify_email": reminder.notify_email,
            "is_active": reminder.is_active,
            "taken_today": reminder.last_taken_on == date.today(),
            "last_sent_on": reminder.last_sent_on.isoformat() if reminder.last_sent_on else None,
            "last_taken_on": reminder.last_taken_on.isoformat() if reminder.last_taken_on else None,
            "created_at": reminder.created_at.isoformat() if reminder.created_at else None,
        }

    def list_for_user(self, user_id: int) -> list[dict]:
        reminders = self.reminder_repo.list_for_user(user_id)
        return [self.serialize(reminder) for reminder in reminders]

    def create_for_user(
        self,
        *,
        user_id: int,
        name: str,
        dose: str,
        time_of_day: str,
        recurrence: str,
        notify_email: str | None,
    ) -> MedicineReminderModel:
        name = str(name or "").strip()
        dose = str(dose or "").strip() or "1 dose"
        time_of_day = str(time_of_day or "").strip()
        recurrence = str(recurrence or "daily").strip().lower()
        notify_email = str(notify_email or "").strip() or None

        if not name:
            raise ValueError("Medicine name is required")
        if len(name) > 60:
            raise ValueError("Medicine name must not exceed 60 characters")
        if len(dose) > 80:
            raise ValueError("Dosage must not exceed 80 characters")
        if not _TIME_RE.match(time_of_day):
            raise ValueError("Time must use HH:MM format")
        if recurrence not in {"daily", "weekday", "weekend"}:
            raise ValueError("Days must be one of: daily, weekday, weekend")
        if notify_email and "@" not in notify_email:
            raise ValueError("Notify email is not valid")

        reminder = self.reminder_repo.create(
            user_id=user_id,
            medicine_name=name,
            dosage=dose,
            time_of_day=time_of_day,
            recurrence=recurrence,
            notify_email=notify_email,
        )
        db.session.commit()
        return reminder

    def set_taken(self, reminder_id: int, user_id: int, taken: bool) -> MedicineReminderModel | None:
        reminder = self.reminder_repo.find_by_id_and_user(reminder_id, user_id)
        if not reminder:
            return None
        reminder.last_taken_on = date.today() if taken else None
        db.session.commit()
        return reminder

    def delete(self, reminder_id: int, user_id: int) -> bool:
        reminder = self.reminder_repo.find_by_id_and_user(reminder_id, user_id)
        if not reminder:
            return False
        self.reminder_repo.delete(reminder)
        db.session.commit()
        return True

    def dispatch_due_reminders(self, now: datetime | None = None) -> int:
        now = now or datetime.now()
        today = now.date()
        # Window ±1 phút để tránh miss reminder khi cron lệch giây
        candidates = {
            (now + timedelta(minutes=delta)).strftime("%H:%M")
            for delta in (-1, 0, 1)
        }
        due_reminders = self.reminder_repo.get_due(candidates)

        dispatched = 0
        try:
            for reminder in due_reminders:
                if reminder.last_sent_on == today:
                    continue
                if not self._matches_recurrence(reminder.recurrence, today):
                    continue

                user_email = self.reminder_repo.get_user_email(reminder.user_id)
                recipients = self.email_notifier.resolve_recipients(
                    user_email=user_email,
                    extra=reminder.notify_email,
                )
                subject = f"Medicine Reminder: {reminder.medicine_name}"
                body = (
                    f"Medication reminder for {reminder.medicine_name}\n\n"
                    f"Dosage: {reminder.dosage}\n"
                    f"Scheduled time: {reminder.time_of_day}\n"
                    f"Schedule: {reminder.recurrence}\n"
                    f"Generated at: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                delivery = self.email_notifier.send_message(subject=subject, body=body, recipients=recipients)

                alert_message = (
                    f"Medicine reminder: {reminder.medicine_name} ({reminder.dosage}) at {reminder.time_of_day}."
                )
                if delivery.get("sent"):
                    alert_message += f" Email sent to {len(delivery.get('recipients', []))} recipient(s)."
                else:
                    alert_message += " Email delivery unavailable."

                self.alert_usecase.create_alert(
                    device_code="MEDICINE",
                    message=alert_message[:255],
                    level="warning",
                    user_id=reminder.user_id,
                )
                reminder.last_sent_on = today
                dispatched += 1

            if dispatched:
                db.session.commit()
        except Exception:
            db.session.rollback()
            logger.error("Medicine reminder dispatch failed", exc_info=True)
            return 0
        return dispatched

    @staticmethod
    def _matches_recurrence(recurrence: str, current_date: date) -> bool:
        weekday = current_date.weekday()
        if recurrence == "weekday":
            return weekday < 5
        if recurrence == "weekend":
            return weekday >= 5
        return True