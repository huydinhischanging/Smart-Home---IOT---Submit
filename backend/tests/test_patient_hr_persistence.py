"""Tests for patient_hr_persistence — persist_patient_hr_record function."""
import time
from unittest.mock import MagicMock, patch
import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from app.extensions.database import db
from app.infrastructure.persistence.models.user_model import UserModel
from app.infrastructure.persistence.models.patient_profile_model import PatientProfileModel
from app.infrastructure.persistence.models.patient_hr_record_model import PatientHeartRateRecordModel
from app.usecases.patient_hr_persistence import persist_patient_hr_record, _last_saved_at_by_user


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

def _make_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    db.init_app(app)
    return app


def _seed_user(app, username="testuser", role="user"):
    with app.app_context():
        user = UserModel(
            username=username,
            email=f"{username}@test.com",
            role=role,
            is_active=True,
            password=generate_password_hash("password123"),
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return user_id


# ---------------------------------------------------------------------------
# persist_patient_hr_record
# ---------------------------------------------------------------------------

class TestPersistPatientHrRecord:
    def test_returns_zero_for_invalid_bpm(self):
        app = _make_app()
        with app.app_context():
            db.create_all()
            result = persist_patient_hr_record("not-a-number")
        assert result == 0

    def test_returns_zero_when_no_active_users(self):
        app = _make_app()
        with app.app_context():
            db.create_all()
            result = persist_patient_hr_record(75)
        assert result == 0

    def test_saves_record_for_active_user(self):
        app = _make_app()
        with app.app_context():
            db.create_all()
        user_id = _seed_user(app)
        _last_saved_at_by_user.clear()

        with app.app_context():
            result = persist_patient_hr_record(75, force=True)
            assert result >= 1
            record = PatientHeartRateRecordModel.query.filter_by(user_id=user_id).first()
            assert record is not None
            assert record.bpm == 75

    def test_saves_severity(self):
        app = _make_app()
        with app.app_context():
            db.create_all()
        user_id = _seed_user(app, username="sev_user")
        _last_saved_at_by_user.clear()

        with app.app_context():
            persist_patient_hr_record(120, severity="high", force=True)
            record = PatientHeartRateRecordModel.query.filter_by(user_id=user_id).first()
            assert record.severity == "high"

    def test_saves_hrv_metrics(self):
        app = _make_app()
        with app.app_context():
            db.create_all()
        user_id = _seed_user(app, username="hrv_user")
        _last_saved_at_by_user.clear()

        with app.app_context():
            persist_patient_hr_record(
                75,
                hrv_rmssd=35.5,
                hrv_sdnn=55.0,
                hrv_pnn50=15.0,
                hrv_mean_rr=800.0,
                hrv_risk="normal",
                force=True,
            )
            record = PatientHeartRateRecordModel.query.filter_by(user_id=user_id).first()
            assert record.hrv_rmssd == 35.5
            assert record.hrv_risk == "normal"

    def test_throttle_prevents_duplicate_saves(self):
        app = _make_app()
        with app.app_context():
            db.create_all()
        user_id = _seed_user(app, username="throttle_user")
        _last_saved_at_by_user.clear()

        with app.app_context():
            # First save: should go through
            r1 = persist_patient_hr_record(75, throttle_sec=60)
            # Second save immediately: should be throttled
            r2 = persist_patient_hr_record(76, throttle_sec=60)
            assert r1 >= 1
            assert r2 == 0

    def test_force_bypasses_throttle(self):
        app = _make_app()
        with app.app_context():
            db.create_all()
        user_id = _seed_user(app, username="force_user")
        _last_saved_at_by_user.clear()

        with app.app_context():
            r1 = persist_patient_hr_record(75, throttle_sec=60, force=True)
            r2 = persist_patient_hr_record(76, throttle_sec=60, force=True)
            assert r1 >= 1
            assert r2 >= 1

    def test_inactive_user_not_saved(self):
        app = _make_app()
        with app.app_context():
            db.create_all()
            user = UserModel(
                username="inactive_user",
                email="inactive@test.com",
                role="user",
                is_active=False,
                password=generate_password_hash("password123"),
            )
            db.session.add(user)
            db.session.commit()

        _last_saved_at_by_user.clear()
        with app.app_context():
            result = persist_patient_hr_record(75, force=True)
        assert result == 0

    def test_source_defaults_to_coospo_backend(self):
        app = _make_app()
        with app.app_context():
            db.create_all()
        user_id = _seed_user(app, username="src_user")
        _last_saved_at_by_user.clear()

        with app.app_context():
            persist_patient_hr_record(80, force=True)
            record = PatientHeartRateRecordModel.query.filter_by(user_id=user_id).first()
            assert record.source == "coospo_backend"

    def test_custom_source_saved(self):
        app = _make_app()
        with app.app_context():
            db.create_all()
        user_id = _seed_user(app, username="custom_src_user")
        _last_saved_at_by_user.clear()

        with app.app_context():
            persist_patient_hr_record(80, source="manual", force=True)
            record = PatientHeartRateRecordModel.query.filter_by(user_id=user_id).first()
            assert record.source == "manual"

    def test_converts_float_bpm_to_int(self):
        app = _make_app()
        with app.app_context():
            db.create_all()
        user_id = _seed_user(app, username="float_bpm_user")
        _last_saved_at_by_user.clear()

        with app.app_context():
            persist_patient_hr_record(72.9, force=True)
            record = PatientHeartRateRecordModel.query.filter_by(user_id=user_id).first()
            assert record.bpm == 72
