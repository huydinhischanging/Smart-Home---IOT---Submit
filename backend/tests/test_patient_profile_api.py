from flask import Flask
from werkzeug.security import generate_password_hash

from app.extensions.database import db
from app.infrastructure.persistence.models.patient_profile_model import PatientProfileModel
from app.infrastructure.persistence.models.user_model import UserModel
from app.presentation.api.auth_api import _make_token
from app.presentation.api.patient_report_api import patient_report_api


def _make_user(app, username="elder-user", email="elder@example.com"):
    with app.app_context():
        user = UserModel(
            username=username,
            email=email,
            password=generate_password_hash("Password123"),
            role="user",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        token = _make_token(user)
        return user, token


def _make_profile_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    db.init_app(app)
    app.register_blueprint(patient_report_api, url_prefix="/api/patient")
    return app


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_get_profile_requires_bearer_token():
    app = _make_profile_app()

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        response = client.get("/api/patient/profile")

        assert response.status_code == 401
        assert response.get_json()["message"] == "Authentication required"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_get_profile_returns_none_when_profile_missing():
    app = _make_profile_app()

    with app.app_context():
        db.create_all()
        _, token = _make_user(app)

    try:
        client = app.test_client()
        response = client.get("/api/patient/profile", headers=_auth_headers(token))

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["status"] == "success"
        assert payload["profile"] is None
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_put_profile_creates_and_returns_profile():
    app = _make_profile_app()

    with app.app_context():
        db.create_all()
        user, token = _make_user(app)

    try:
        client = app.test_client()
        response = client.put(
            "/api/patient/profile",
            headers=_auth_headers(token),
            json={
                "patient_name": "Bruce Wayne",
                "age": 78,
                "gender": "male",
                "baseline_hr_rest": 62,
                "baseline_hr_min": 52,
                "baseline_hr_max": 108,
                "diagnosis_notes": "Monitor hydration and sleep quality.",
                "medications": "Morning beta blocker",
                "consent_analytics": True,
                "consent_pdf_export": False,
            },
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["status"] == "success"
        assert payload["profile"]["user_id"] == user.id
        assert payload["profile"]["patient_name"] == "Bruce Wayne"
        assert payload["profile"]["age"] == 78
        assert payload["profile"]["consent_pdf_export"] is False

        with app.app_context():
            profile = PatientProfileModel.query.filter_by(user_id=user.id).first()
            assert profile is not None
            assert profile.patient_name == "Bruce Wayne"
            assert profile.baseline_hr_rest == 62
            assert profile.consent_pdf_export is False
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_put_profile_updates_existing_record_without_creating_duplicate():
    app = _make_profile_app()

    with app.app_context():
        db.create_all()
        user, token = _make_user(app)
        db.session.add(
            PatientProfileModel(
                user_id=user.id,
                patient_name="Bruce Wayne",
                age=78,
                consent_pdf_export=True,
            )
        )
        db.session.commit()

    try:
        client = app.test_client()
        response = client.put(
            "/api/patient/profile",
            headers=_auth_headers(token),
            json={
                "patient_name": "Alfred Pennyworth",
                "age": 79,
                "consent_pdf_export": False,
            },
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["profile"]["patient_name"] == "Alfred Pennyworth"
        assert payload["profile"]["age"] == 79
        assert payload["profile"]["consent_pdf_export"] is False

        with app.app_context():
            profiles = PatientProfileModel.query.filter_by(user_id=user.id).all()
            assert len(profiles) == 1
            assert profiles[0].patient_name == "Alfred Pennyworth"

        get_response = client.get("/api/patient/profile", headers=_auth_headers(token))
        assert get_response.status_code == 200
        assert get_response.get_json()["profile"]["patient_name"] == "Alfred Pennyworth"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()