from datetime import datetime, timezone

from app.extensions.database import db


class PatientHeartRateRecordModel(db.Model):
    __tablename__ = "patient_hr_records"

    __table_args__ = (
        db.Index("idx_patient_hr_user_time", "user_id", "recorded_at"),
        db.Index("idx_patient_hr_severity", "severity"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    bpm = db.Column(db.Integer, nullable=False)
    severity = db.Column(db.String(20), nullable=False, default="normal")
    risk = db.Column(db.String(30), nullable=True)
    mood = db.Column(db.String(30), nullable=True)
    source = db.Column(db.String(30), nullable=False, default="manual")
    note = db.Column(db.String(255), nullable=True)

    # HRV metrics (Heart Rate Variability) — for BME conference evaluation
    hrv_rmssd = db.Column(db.Float, nullable=True)   # ms — parasympathetic tone
    hrv_sdnn  = db.Column(db.Float, nullable=True)   # ms — overall HRV
    hrv_pnn50 = db.Column(db.Float, nullable=True)   # %  — vagal activity
    hrv_mean_rr = db.Column(db.Float, nullable=True) # ms — mean RR interval
    hrv_risk  = db.Column(db.String(30), nullable=True)  # normal/low_hrv/very_low_hrv

    recorded_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("UserModel", backref=db.backref("hr_records", lazy="dynamic", passive_deletes=True))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "bpm": self.bpm,
            "severity": self.severity,
            "risk": self.risk,
            "mood": self.mood,
            "source": self.source,
            "note": self.note,
            "hrv": {
                "rmssd_ms":   self.hrv_rmssd,
                "sdnn_ms":    self.hrv_sdnn,
                "pnn50_pct":  self.hrv_pnn50,
                "mean_rr_ms": self.hrv_mean_rr,
                "risk_level": self.hrv_risk,
            } if self.hrv_rmssd is not None else None,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
