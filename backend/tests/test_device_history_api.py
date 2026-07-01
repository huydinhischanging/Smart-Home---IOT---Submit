import importlib

from flask import Flask

from app.extensions.database import db
from app.extensions.limiter import limiter
from app.gateways.mqtt_publisher import MqttPublisher
from app.infrastructure.persistence.models import ControlLog, Device, UserModel
from app.infrastructure.persistence.repositories.device_repository import DeviceRepository
from app.infrastructure.persistence.repositories.log_repository import ControlLogRepository
from app.infrastructure.persistence.repositories.sensor_repository import SensorRepository
from app.infrastructure.persistence.repositories.status_repository import DeviceStatusRepository
from app.presentation.api.auth_api import auth_api
from app.presentation.api.device_api import device_api
from app.usecases.device_usecase import DeviceUseCase


device_api_module = importlib.import_module("app.presentation.api.device_api")


class _DummyRealtimeNotifier:
    def notify_device_status(self, payload, user_id=None):
        return None

    def notify_device_list_changed(self, user_id=None):
        return None


class _DummyMqttPublisher(MqttPublisher):
    def __init__(self):
        self.commands = []

    def send_device_command(self, device_code: str, payload: str) -> bool:
        self.commands.append({"device_code": device_code, "payload": payload})
        return True


def _make_device_app(monkeypatch):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
        RATELIMIT_ENABLED=False,
    )
    db.init_app(app)
    limiter.init_app(app)
    app.register_blueprint(auth_api, url_prefix="/api/auth")
    app.register_blueprint(device_api)

    device_repo = DeviceRepository()
    log_repo = ControlLogRepository()
    sensor_repo = SensorRepository()
    usecase = DeviceUseCase(
        device_repo=device_repo,
        status_repo=DeviceStatusRepository(),
        log_repo=log_repo,
        mqtt_publisher=_DummyMqttPublisher(),
        realtime_notifier=_DummyRealtimeNotifier(),
    )

    monkeypatch.setattr(device_api_module.container, "device_usecase", lambda: usecase)
    monkeypatch.setattr(device_api_module.container, "device_repository", lambda: device_repo)
    monkeypatch.setattr(device_api_module.container, "log_repository", lambda: log_repo)
    monkeypatch.setattr(device_api_module.container, "sensor_repository", lambda: sensor_repo)
    monkeypatch.setattr(device_api_module.container, "realtime_notifier", lambda: _DummyRealtimeNotifier())
    return app


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, username, email):
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "Password123",
        },
    )
    assert response.status_code == 201
    return response.get_json()["token"]


def test_device_history_uses_stable_device_id_after_code_reuse(monkeypatch):
    app = _make_device_app(monkeypatch)

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        token = _register(client, "elder-user", "elder@example.com")

        with app.app_context():
            user = UserModel.query.filter_by(email="elder@example.com").one()
            device_repo = DeviceRepository()
            log_repo = ControlLogRepository()

            first_device = device_repo.create(
                name="Lamp",
                code="lamp",
                control_types=["switch"],
                category="light",
                user_id=user.id,
            )
            db.session.flush()
            log_repo.add(
                device_code=first_device.code,
                device_id=first_device.id,
                action="CONTROL: ON",
                source="API",
            )
            device_repo.delete(first_device)

            second_device = device_repo.create(
                name="Lamp",
                code="lamp",
                control_types=["switch"],
                category="light",
                user_id=user.id,
            )
            db.session.flush()
            log_repo.add(
                device_code=second_device.code,
                device_id=second_device.id,
                action="CONTROL: OFF",
                source="API",
            )
            db.session.commit()

            assert ControlLog.query.count() == 2
            assert Device.query.filter(Device.code == "lamp", Device.is_deleted == False).count() == 1

        response = client.get(
            "/api/devices/lamp/history",
            headers=_bearer(token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert len(payload["data"]) == 1
        assert payload["data"][0]["action"] == "CONTROL: OFF"
        assert payload["data"][0]["device_code"] == "lamp"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_sensor_history_v2_returns_sensor_data(monkeypatch):
    app = _make_device_app(monkeypatch)

    with app.app_context():
        db.create_all()

    try:
        client = app.test_client()
        token = _register(client, "sensor-user", "sensor@example.com")

        with app.app_context():
            user = UserModel.query.filter_by(email="sensor@example.com").one()
            device_repo = DeviceRepository()
            sensor_repo = SensorRepository()

            device = device_repo.create(
                name="Do am A1",
                code="do_am_a1",
                control_types=["humidity"],
                category="sensor",
                device_type="humidity",
                metadata_json={"unit": "%"},
                user_id=user.id,
            )
            db.session.flush()
            sensor_repo.save(device.id, 65.0)
            sensor_repo.save(device.id, 66.5)
            db.session.commit()

        response = client.get(
            "/api/devices/sensors/humidity/do_am_a1/history",
            headers=_bearer(token),
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert len(payload["data"]) == 2
        assert payload["data"][0]["device_code"] == "do_am_a1"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()