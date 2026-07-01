# app/infrastructure/persistence/repositories/medicine_reminder_repository.py
from typing import Optional, List
from app.extensions.database import db
from app.infrastructure.persistence.models.medicine_reminder_model import MedicineReminderModel
from app.infrastructure.persistence.models.user_model import UserModel


class MedicineReminderRepository:

    def list_for_user(self, user_id: int) -> List[MedicineReminderModel]:
        return (
            MedicineReminderModel.query
            .filter_by(user_id=user_id)
            .order_by(MedicineReminderModel.time_of_day.asc(), MedicineReminderModel.id.asc())
            .all()
        )

    def create(
        self, *,
        user_id: int,
        medicine_name: str,
        dosage: str,
        time_of_day: str,
        recurrence: str,
        notify_email: Optional[str],
        is_active: bool = True,
    ) -> MedicineReminderModel:
        reminder = MedicineReminderModel(
            user_id=user_id,
            medicine_name=medicine_name,
            dosage=dosage,
            time_of_day=time_of_day,
            recurrence=recurrence,
            notify_email=notify_email,
            is_active=is_active,
        )
        db.session.add(reminder)
        db.session.flush()
        return reminder

    def find_by_id_and_user(self, reminder_id: int, user_id: int) -> Optional[MedicineReminderModel]:
        return MedicineReminderModel.query.filter_by(id=reminder_id, user_id=user_id).first()

    def delete(self, reminder: MedicineReminderModel) -> None:
        db.session.delete(reminder)
        db.session.flush()

    def get_due(self, time_candidates: set) -> List[MedicineReminderModel]:
        return MedicineReminderModel.query.filter(
            MedicineReminderModel.is_active == True,
            MedicineReminderModel.time_of_day.in_(time_candidates),
        ).all()

    def get_user_email(self, user_id: int) -> Optional[str]:
        user = db.session.get(UserModel, user_id)
        return user.email if user else None
