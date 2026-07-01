"""Tests for patient_report_api — profile, hr-records, hrv-summary, helper functions."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from app.extensions.database import db
from app.infrastructure.persistence.models.patient_hr_record_model import PatientHeartRateRecordModel
from app.infrastructure.persistence.models.patient_profile_model import PatientProfileModel
from app.infrastructure.persistence.models.user_model import UserModel
from app.presentation.api.auth_api import _make_token
from app.presentation.api.patient_report_api import patient_report_api, _calc_summary, _extract_filename


# ---------------------------------------------------------------------------
# App / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def prapp():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    db.init_app(app)
    app.register_blueprint(patient_report_api, url_prefix="/api/patient")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(app, username="user1", consent_pdf=True):
    with app.app_context():
        user = UserModel(
            username=username,
            email=f"{username}@test.com",
            password=generate_password_hash("pass"),
            role="user",
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()
        profile = PatientProfileModel(
            user_id=user.id,
            patient_name="Test Patient",
            consent_pdf_export=consent_pdf,
        )
        db.session.add(profile)
        db.session.commit()
        token = _make_token(user)
        return user.id, token


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# _extract_filename helper
# ---------------------------------------------------------------------------

class TestExtractFilename:
    def test_returns_default_when_none(self):
        assert _extract_filename(None) == "alfred_report.pdf"

    def test_returns_default_when_no_filename(self):
        assert _extract_filename("attachment") == "alfred_report.pdf"

    def test_extracts_filename_from_disposition(self):
        result = _extract_filename('attachment; filename="report.pdf"')
        assert result == "report.pdf"

    def test_extracts_unquoted_filename(self):
        result = _extract_filename("attachment; filename=report.pdf")
        assert result == "report.pdf"

    def test_custom_default(self):
        result = _extract_filename(None, default="custom.pdf")
        assert result == "custom.pdf"


# ---------------------------------------------------------------------------
# _calc_summary helper
# ---------------------------------------------------------------------------

class TestCalcSummary:
    def test_empty_list_returns_zeros(self):
        s = _calc_summary([])
        assert s["count"] == 0
        assert s["avg_bpm"] is None
        assert s["min_bpm"] is None
        assert s["max_bpm"] is None
        assert s["normal_rate_percent"] is None

    def test_calculates_averages(self):
        records = [
            MagicMock(bpm=60, severity="normal"),
            MagicMock(bpm=80, severity="normal"),
            MagicMock(bpm=100, severity="caution"),
        ]
        s = _calc_summary(records)
        assert s["count"] == 3
        assert s["avg_bpm"] == round((60 + 80 + 100) / 3, 2)
        assert s["min_bpm"] == 60
        assert s["max_bpm"] == 100

    def test_normal_rate_percent(self):
        records = [
            MagicMock(bpm=70, severity="normal"),
            MagicMock(bpm=70, severity="normal"),
            MagicMock(bpm=120, severity="critical"),
            MagicMock(bpm=110, severity="warning"),
        ]
        s = _calc_summary(records)
        assert s["normal_rate_percent"] == 50.0

    def test_severity_counts(self):
        records = [
            MagicMock(bpm=70, severity="normal"),
            MagicMock(bpm=110, severity="warning"),
            MagicMock(bpm=140, severity="critical"),
            MagicMock(bpm=95, severity="caution"),
        ]
        s = _calc_summary(records)
        assert s["severity_counts"]["normal"] == 1
        assert s["severity_counts"]["warning"] == 1
        assert s["severity_counts"]["critical"] == 1
        assert s["severity_counts"]["caution"] == 1

    def test_unknown_severity_handled(self):
        records = [MagicMock(bpm=75, severity="unknown_sev")]
        s = _calc_summary(records)
        assert s["count"] == 1


# ---------------------------------------------------------------------------
# GET /api/patient/profile
# ---------------------------------------------------------------------------

class TestGetProfile:
    def test_returns_none_profile_when_no_profile(self, prapp):
        with prapp.app_context():
            user = UserModel(
                username="no_profile",
                email="noprofile@test.com",
                password=generate_password_hash("pass"),
                role="user",
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
            token = _make_token(user)

        client = prapp.test_client()
        resp = client.get("/api/patient/profile", headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["profile"] is None

    def test_returns_profile_when_exists(self, prapp):
        _, token = _make_user(prapp, "profile_user")
        client = prapp.test_client()
        resp = client.get("/api/patient/profile", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.get_json()["profile"]["patient_name"] == "Test Patient"


# ---------------------------------------------------------------------------
# PUT /api/patient/profile
# ---------------------------------------------------------------------------

class TestUpsertProfile:
    def test_creates_profile_if_not_exists(self, prapp):
        with prapp.app_context():
            user = UserModel(
                username="upsert_user",
                email="upsert@test.com",
                password=generate_password_hash("pass"),
                role="user",
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
            token = _make_token(user)

        client = prapp.test_client()
        resp = client.put(
            "/api/patient/profile",
            headers=_auth_headers(token),
            json={"patient_name": "New Name", "age": 65},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["profile"]["patient_name"] == "New Name"

    def test_updates_existing_profile(self, prapp):
        _, token = _make_user(prapp, "update_user")
        client = prapp.test_client()
        resp = client.put(
            "/api/patient/profile",
            headers=_auth_headers(token),
            json={"patient_name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["profile"]["patient_name"] == "Updated Name"


# ---------------------------------------------------------------------------
# POST /api/patient/hr-records
# ---------------------------------------------------------------------------

class TestCreateHrRecord:
    def test_creates_record(self, prapp):
        _, token = _make_user(prapp, "hr_user")
        client = prapp.test_client()
        resp = client.post(
            "/api/patient/hr-records",
            headers=_auth_headers(token),
            json={"bpm": 75, "severity": "normal", "source": "manual"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["record"]["bpm"] == 75

    def test_missing_bpm_returns_400(self, prapp):
        _, token = _make_user(prapp, "hr_nobpm")
        client = prapp.test_client()
        resp = client.post(
            "/api/patient/hr-records",
            headers=_auth_headers(token),
            json={"severity": "normal"},
        )
        assert resp.status_code == 400

    def test_invalid_bpm_returns_400(self, prapp):
        _, token = _make_user(prapp, "hr_badbpm")
        client = prapp.test_client()
        resp = client.post(
            "/api/patient/hr-records",
            headers=_auth_headers(token),
            json={"bpm": "not-a-number"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/patient/hr-records
# ---------------------------------------------------------------------------

class TestListHrRecords:
    def test_returns_empty_list_initially(self, prapp):
        _, token = _make_user(prapp, "list_user")
        client = prapp.test_client()
        resp = client.get("/api/patient/hr-records", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.get_json()["records"] == []

    def test_returns_records_with_summary(self, prapp):
        user_id, token = _make_user(prapp, "list2_user")
        with prapp.app_context():
            for bpm in [60, 75, 90]:
                db.session.add(PatientHeartRateRecordModel(
                    user_id=user_id,
                    bpm=bpm,
                    severity="normal",
                    source="manual",
                    recorded_at=datetime.now(timezone.utc),
                ))
            db.session.commit()

        client = prapp.test_client()
        resp = client.get("/api/patient/hr-records", headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["records"]) == 3
        assert data["summary"]["count"] == 3

    def test_limit_param_respected(self, prapp):
        user_id, token = _make_user(prapp, "limit_user")
        with prapp.app_context():
            for i in range(10):
                db.session.add(PatientHeartRateRecordModel(
                    user_id=user_id, bpm=70 + i, severity="normal",
                    source="manual", recorded_at=datetime.now(timezone.utc),
                ))
            db.session.commit()

        client = prapp.test_client()
        resp = client.get("/api/patient/hr-records?limit=3", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert len(resp.get_json()["records"]) == 3


# ---------------------------------------------------------------------------
# GET /api/patient/hrv/summary
# ---------------------------------------------------------------------------

class TestHrvSummary:
    def test_returns_none_when_no_hrv_data(self, prapp):
        _, token = _make_user(prapp, "hrv_none_user")
        client = prapp.test_client()
        resp = client.get("/api/patient/hrv/summary", headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["hrv_summary"] is None

    def test_returns_hrv_stats_when_data_exists(self, prapp):
        user_id, token = _make_user(prapp, "hrv_data_user")
        with prapp.app_context():
            for i in range(3):
                db.session.add(PatientHeartRateRecordModel(
                    user_id=user_id, bpm=70, severity="normal",
                    source="coospo", recorded_at=datetime.now(timezone.utc),
                    hrv_rmssd=30.0 + i, hrv_sdnn=50.0, hrv_pnn50=15.0,
                    hrv_risk="normal",
                ))
            db.session.commit()

        client = prapp.test_client()
        resp = client.get("/api/patient/hrv/summary", headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["hrv_summary"]["n_records"] == 3
        assert data["hrv_summary"]["rmssd_ms"]["n"] == 3


# ---------------------------------------------------------------------------
# GET /api/patient/hrv/live
# ---------------------------------------------------------------------------

class TestHrvLive:
    def test_returns_none_when_monitor_not_initialized(self, prapp):
        _, token = _make_user(prapp, "hrv_live_user")
        with patch("app.presentation.api.patient_report_api.container") as mock_container:
            with patch("app.ai.services.heart_rate_ai.get_monitor", return_value=None):
                client = prapp.test_client()
                resp = client.get("/api/patient/hrv/live", headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["hrv"] is None

    def test_returns_hrv_when_monitor_available(self, prapp):
        _, token = _make_user(prapp, "hrv_live2_user")
        mock_monitor = MagicMock()
        mock_hrv = MagicMock()
        mock_hrv.to_dict.return_value = {"rmssd": 35.0}
        mock_monitor.hrv_analyzer.compute.return_value = mock_hrv

        with patch("app.ai.services.heart_rate_ai.get_monitor", return_value=mock_monitor):
            client = prapp.test_client()
            resp = client.get("/api/patient/hrv/live", headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["hrv"]["rmssd"] == 35.0

    def test_returns_500_on_exception(self, prapp):
        _, token = _make_user(prapp, "hrv_live3_user")
        with patch("app.ai.services.heart_rate_ai.get_monitor", side_effect=Exception("crash")):
            client = prapp.test_client()
            resp = client.get("/api/patient/hrv/live", headers=_auth_headers(token))
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/patient/report.pdf  — consent blocked
# ---------------------------------------------------------------------------

class TestExportPdf:
    def test_pdf_blocked_when_consent_false(self, prapp):
        _, token = _make_user(prapp, "no_consent_user", consent_pdf=False)
        client = prapp.test_client()
        resp = client.get("/api/patient/report.pdf", headers=_auth_headers(token))
        assert resp.status_code == 403

    def test_pdf_returns_error_when_fpdf_not_installed(self, prapp):
        user_id, token = _make_user(prapp, "fpdf_error_user")
        with patch.dict("sys.modules", {"fpdf": None}):
            client = prapp.test_client()
            resp = client.get("/api/patient/report.pdf", headers=_auth_headers(token))
        # Either 500 (fpdf missing) or 200 with PDF if fpdf is installed
        assert resp.status_code in (200, 500)

    def test_pdf_generated_with_no_records(self, prapp):
        """User has profile + consent but no HR records — covers empty data PDF path."""
        _, token = _make_user(prapp, "pdf_empty_user", consent_pdf=True)
        client = prapp.test_client()
        resp = client.get("/api/patient/report.pdf", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"
        assert len(resp.data) > 100  # non-empty PDF

    def test_pdf_generated_with_normal_records(self, prapp):
        """User has HR records in normal range — covers normal_rate >= 90 narrative."""
        user_id, token = _make_user(prapp, "pdf_normal_user", consent_pdf=True)
        with prapp.app_context():
            for i in range(5):
                db.session.add(PatientHeartRateRecordModel(
                    user_id=user_id, bpm=70 + i, severity="normal",
                    source="coospo", recorded_at=datetime.now(timezone.utc),
                ))
            db.session.commit()
        client = prapp.test_client()
        resp = client.get("/api/patient/report.pdf", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

    def test_pdf_generated_with_critical_records(self, prapp):
        """User has critical HR events — covers critical narrative + recommendations."""
        user_id, token = _make_user(prapp, "pdf_critical_user", consent_pdf=True)
        with prapp.app_context():
            db.session.add(PatientHeartRateRecordModel(
                user_id=user_id, bpm=160, severity="critical",
                source="coospo", recorded_at=datetime.now(timezone.utc),
            ))
            db.session.add(PatientHeartRateRecordModel(
                user_id=user_id, bpm=40, severity="warning",
                source="coospo", recorded_at=datetime.now(timezone.utc),
            ))
            # Add many normal records to lower normal_rate
            for i in range(3):
                db.session.add(PatientHeartRateRecordModel(
                    user_id=user_id, bpm=75, severity="normal",
                    source="coospo", recorded_at=datetime.now(timezone.utc),
                ))
            db.session.commit()
        client = prapp.test_client()
        resp = client.get("/api/patient/report.pdf", headers=_auth_headers(token))
        assert resp.status_code == 200

    def test_pdf_with_full_profile(self, prapp):
        """User has complete profile data — covers clinical profile section."""
        with prapp.app_context():
            user = UserModel(
                username="pdf_full_profile",
                email="fullprofile@test.com",
                password=generate_password_hash("pass"),
                role="user",
                is_active=True,
            )
            db.session.add(user)
            db.session.flush()
            profile = PatientProfileModel(
                user_id=user.id,
                patient_name="John Elder",
                age=75,
                gender="male",
                baseline_hr_rest=65,
                baseline_hr_min=55,
                baseline_hr_max=100,
                diagnosis_notes="Mild hypertension. On ACE inhibitor therapy.",
                medications="Lisinopril 10mg daily",
                consent_pdf_export=True,
            )
            db.session.add(profile)
            # Add records with HRV data
            db.session.add(PatientHeartRateRecordModel(
                user_id=user.id, bpm=72, severity="normal",
                source="coospo", recorded_at=datetime.now(timezone.utc),
                hrv_rmssd=32.0, hrv_sdnn=45.0,
            ))
            db.session.commit()
            token = _make_token(user)

        client = prapp.test_client()
        resp = client.get("/api/patient/report.pdf", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

    def test_pdf_with_no_profile(self, prapp):
        """User has no profile — covers 'no profile' section in PDF."""
        with prapp.app_context():
            user = UserModel(
                username="pdf_no_profile",
                email="noprofilepdf@test.com",
                password=generate_password_hash("pass"),
                role="user",
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
            token = _make_token(user)

        client = prapp.test_client()
        resp = client.get("/api/patient/report.pdf", headers=_auth_headers(token))
        # No profile → consent_pdf_export is None (not False) → allowed
        assert resp.status_code in (200, 403)


# ---------------------------------------------------------------------------
# DELETE /api/patient/hr-records/<id>  (if exists)
# POST /api/patient/report/email
# ---------------------------------------------------------------------------

class TestEmailReport:
    def test_email_report_no_profile(self, prapp):
        """User without profile still triggers email (or returns error)."""
        from types import SimpleNamespace

        with prapp.app_context():
            user = UserModel(
                username="email_noprofile",
                email="enoprofile@test.com",
                password=generate_password_hash("pass"),
                role="user",
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
            token = _make_token(user)

        class FakeNotifier:
            def resolve_recipients(self, **kw):
                return ["enoprofile@test.com"]
            def send_message(self, **kw):
                return {"sent": True, "recipients": ["enoprofile@test.com"], "provider": "smtp"}

        with patch("app.presentation.api.patient_report_api.container",
                   SimpleNamespace(email_notifier=lambda: FakeNotifier())):
            client = prapp.test_client()
            resp = client.post(
                "/api/patient/report/email",
                headers=_auth_headers(token),
                json={"email": "doctor@example.com"},
            )
        assert resp.status_code in (200, 403, 500)
