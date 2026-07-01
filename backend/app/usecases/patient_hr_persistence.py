import threading
import time

from app.extensions.database import db
from app.infrastructure.persistence.models.patient_hr_record_model import PatientHeartRateRecordModel
from app.infrastructure.persistence.models.patient_profile_model import PatientProfileModel
from app.infrastructure.persistence.models.user_model import UserModel


_last_saved_at_by_user: dict[int, float] = {}
_throttle_lock = threading.Lock()


def _target_users():
    profiles = (
        PatientProfileModel.query
        .join(UserModel, UserModel.id == PatientProfileModel.user_id)
        .filter(PatientProfileModel.consent_analytics.is_(True))
        .filter(UserModel.is_active.is_(True))
        .filter(UserModel.role == "user")
        .all()
    )

    users = [profile.user for profile in profiles if profile.user is not None]
    if users:
        return users

    return (
        UserModel.query
        .filter(UserModel.is_active.is_(True))
        .filter(UserModel.role == "user")
        .all()
    )


def persist_patient_hr_record(
    bpm,
    *,
    severity="normal",
    risk=None,
    mood=None,
    source="coospo_backend",
    note=None,
    throttle_sec=10,
    force=False,
    hrv_rmssd=None,
    hrv_sdnn=None,
    hrv_pnn50=None,
    hrv_mean_rr=None,
    hrv_risk=None,
):
    try:
        bpm = int(bpm)
    except Exception:
        return 0

    saved_count = 0
    now = time.time()

    for user in _target_users():
        with _throttle_lock:
            if not force:
                last_saved_at = _last_saved_at_by_user.get(user.id, 0)
                if now - last_saved_at < throttle_sec:
                    continue
            _last_saved_at_by_user[user.id] = now
            if len(_last_saved_at_by_user) > 1000:
                oldest = sorted(_last_saved_at_by_user, key=_last_saved_at_by_user.get)[:500]
                for k in oldest:
                    del _last_saved_at_by_user[k]

        record = PatientHeartRateRecordModel(
            user_id=user.id,
            bpm=bpm,
            severity=str(severity or "normal"),
            risk=risk,
            mood=mood,
            source=str(source or "coospo_backend"),
            note=note,
            hrv_rmssd=hrv_rmssd,
            hrv_sdnn=hrv_sdnn,
            hrv_pnn50=hrv_pnn50,
            hrv_mean_rr=hrv_mean_rr,
            hrv_risk=hrv_risk,
        )
        db.session.add(record)
        saved_count += 1

    if saved_count:
        db.session.commit()

    return saved_count