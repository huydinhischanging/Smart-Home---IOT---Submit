# app/infrastructure/persistence/repositories/patient_profile_repository.py
from typing import Optional
from app.infrastructure.persistence.models.patient_profile_model import PatientProfileModel


class PatientProfileRepository:

    def get_display_name(self, user_id: int, fallback: str) -> str:
        profile = PatientProfileModel.query.filter_by(user_id=user_id).first()
        if profile and profile.patient_name:
            return profile.patient_name
        return fallback
