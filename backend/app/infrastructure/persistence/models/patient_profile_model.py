from datetime import datetime, timezone

from app.extensions.database import db


class PatientProfileModel(db.Model):
    __tablename__ = "patient_profiles"

    __table_args__ = (
        db.Index("idx_patient_profile_user", "user_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    patient_name = db.Column(db.String(120), nullable=True)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(30), nullable=True)

    baseline_hr_rest = db.Column(db.Float, nullable=True)
    baseline_hr_min = db.Column(db.Float, nullable=True)
    baseline_hr_max = db.Column(db.Float, nullable=True)

    diagnosis_notes = db.Column(db.Text, nullable=True)
    medications = db.Column(db.Text, nullable=True)

    consent_analytics = db.Column(db.Boolean, nullable=False, default=True)
    consent_pdf_export = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship("UserModel", backref=db.backref("patient_profile", uselist=False, passive_deletes=True))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "patient_name": self.patient_name,
            "age": self.age,
            "gender": self.gender,
            "baseline_hr_rest": self.baseline_hr_rest,
            "baseline_hr_min": self.baseline_hr_min,
            "baseline_hr_max": self.baseline_hr_max,
            "diagnosis_notes": self.diagnosis_notes,
            "medications": self.medications,
            "consent_analytics": self.consent_analytics,
            "consent_pdf_export": self.consent_pdf_export,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
