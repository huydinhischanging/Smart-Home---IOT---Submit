# app/wiring.py
from dependency_injector import containers, providers
import os

from app.usecases.device_usecase import DeviceUseCase
from app.usecases.config_usecase import ConfigUseCase
from app.usecases.realtime_notifier import RealtimeNotifier
from app.usecases.alert_usecase import AlertUseCase
from app.usecases.alert_saved_view_usecase import AlertSavedViewUseCase
from app.usecases.alert_mute_preference_usecase import AlertMutePreferenceUseCase
from app.usecases.medicine_reminder_usecase import MedicineReminderUseCase
from app.usecases.sensor_usecase import SensorUseCase
from app.usecases.ai_usecase import AIUseCase
from app.usecases.room_usecase import RoomUseCase  # ✅ FIX: import RoomUseCase

from app.ai.inference.model_loader import ModelLoader
from app.ai.services.ai_service import AIService
from app.ai.services.alfred_ai import AlfredAiService

from app.infrastructure.persistence.repositories.device_repository import DeviceRepository
from app.infrastructure.persistence.repositories.status_repository import DeviceStatusRepository
from app.infrastructure.persistence.repositories.log_repository import ControlLogRepository
from app.infrastructure.persistence.repositories.sensor_repository import SensorRepository
from app.infrastructure.persistence.repositories.alert_repository import AlertRepository
from app.infrastructure.persistence.repositories.alert_saved_view_repository import AlertSavedViewRepository
from app.infrastructure.persistence.repositories.alert_mute_preference_repository import AlertMutePreferenceRepository
from app.infrastructure.persistence.repositories.room_repository import RoomRepository
from app.infrastructure.persistence.repositories.medicine_reminder_repository import MedicineReminderRepository
from app.infrastructure.config.file_config_repo import FileConfigRepository

from app.gateways.mqtt_publisher import MqttPublisher
from app.gateways.socket_emitter import SocketEmitter
from app.gateways.email_notifier import EmailNotifier


class Container(containers.DeclarativeContainer):

    device_repository = providers.Factory(DeviceRepository)
    status_repository = providers.Factory(DeviceStatusRepository)
    log_repository = providers.Factory(ControlLogRepository)
    sensor_repository = providers.Factory(SensorRepository)
    alert_repository = providers.Factory(AlertRepository)
    alert_saved_view_repository = providers.Factory(AlertSavedViewRepository)
    alert_mute_preference_repository = providers.Factory(AlertMutePreferenceRepository)
    room_repository = providers.Factory(RoomRepository)
    medicine_reminder_repository = providers.Factory(MedicineReminderRepository)

    mqtt_publisher = providers.Singleton(MqttPublisher)
    socket_emitter = providers.Singleton(SocketEmitter)
    email_notifier = providers.Singleton(EmailNotifier)

    realtime_notifier = providers.Singleton(
        RealtimeNotifier,
        socket_emitter=socket_emitter
    )

    device_usecase = providers.Singleton(
        DeviceUseCase,
        device_repo=device_repository,
        status_repo=status_repository,
        log_repo=log_repository,
        mqtt_publisher=mqtt_publisher,
        realtime_notifier=realtime_notifier,
    )

    alert_usecase = providers.Singleton(
        AlertUseCase,
        alert_repo=alert_repository,
        realtime_notifier=realtime_notifier,
    )

    alert_saved_view_usecase = providers.Singleton(
        AlertSavedViewUseCase,
        alert_saved_view_repo=alert_saved_view_repository,
    )

    alert_mute_preference_usecase = providers.Singleton(
        AlertMutePreferenceUseCase,
        alert_mute_pref_repo=alert_mute_preference_repository,
    )

    medicine_reminder_usecase = providers.Singleton(
        MedicineReminderUseCase,
        email_notifier=email_notifier,
        alert_usecase=alert_usecase,
        reminder_repo=medicine_reminder_repository,
    )

    model_loader = providers.Singleton(ModelLoader)
    ai_service = providers.Singleton(AIService, model_loader=model_loader)
    alfred_ai_service = providers.Singleton(AlfredAiService)

    sensor_usecase = providers.Singleton(
        SensorUseCase,
        device_repo=device_repository,
        status_repo=status_repository,
        sensor_repo=sensor_repository,
        alert_repo=alert_repository,
        realtime_notifier=realtime_notifier,
        mqtt_publisher=mqtt_publisher,
    )

    room_usecase = providers.Singleton(RoomUseCase, room_repo=room_repository)

    ai_usecase = providers.Singleton(
        AIUseCase,
        ai_service=ai_service,
        alfred_ai_service=alfred_ai_service,
        alert_usecase=alert_usecase,
        mqtt_publisher=mqtt_publisher,
        realtime_notifier=realtime_notifier,
        device_usecase=device_usecase,
        sensor_usecase=sensor_usecase,
        room_usecase=room_usecase,
        email_notifier=email_notifier,
    )


container = Container()
container.wire(packages=["app.presentation.api", "app.usecases"])

# ✅ Force init AIService ngay lúc startup
import logging as _logging
import threading

_PLACEHOLDER_VALUES = {
    "",
    "your-broker-url-here.emqxsl.com",
    "your-mqtt-username",
    "your-mqtt-password",
    "YOUR_MQTT_USERNAME",
    "YOUR_MQTT_PASSWORD",
}


def _is_placeholder(value):
    return str(value or "").strip() in _PLACEHOLDER_VALUES


def _warmup_ai():
    try:
        container.ai_service()
    except Exception as e:
        _logging.getLogger(__name__).warning("Warmup error: %s", e)
threading.Thread(target=_warmup_ai, daemon=True).start()

def load_broker_config() -> dict:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    repo = FileConfigRepository(base_dir)
    config = ConfigUseCase(repo).load()
    # Env vars take priority over broker_config.json — set them in .env for production.
    url = os.environ.get("MQTT_URL") or config["url"]
    port = int(os.environ.get("MQTT_PORT") or config["port"])
    username = os.environ.get("MQTT_USERNAME") or config.get("username")
    password = os.environ.get("MQTT_PASSWORD") or config.get("password")
    mqtt_enabled_raw = str(os.environ.get("MQTT_ENABLED", "")).strip().lower()
    mqtt_disabled_explicitly = mqtt_enabled_raw in {"0", "false", "no", "off"}
    mqtt_enabled_explicitly = mqtt_enabled_raw in {"1", "true", "yes", "on"}

    if mqtt_disabled_explicitly:
        _logging.getLogger(__name__).info("MQTT is explicitly disabled by MQTT_ENABLED=false.")
        mqtt_enabled = False
    elif mqtt_enabled_explicitly:
        # MQTT_ENABLED=true overrides credential check — supports brokers without auth (local EMQX)
        mqtt_enabled = True
    else:
        # Auto-detect: enable only when url is set and credentials are not placeholders.
        # None username/password means anonymous broker (allowed).
        creds_ok = not any(
            _is_placeholder(v) for v in (url, username, password) if v is not None
        )
        mqtt_enabled = bool(url and not _is_placeholder(url) and creds_ok)

    if not mqtt_enabled and not mqtt_disabled_explicitly:
        _logging.getLogger(__name__).warning(
            "MQTT credentials are missing or placeholder values; MQTT will be disabled in this development session."
        )

    return {
        "MQTT_ENABLED": mqtt_enabled,
        "MQTT_BROKER_URL": url,
        "MQTT_BROKER_PORT": port,
        "MQTT_USERNAME": username,
        "MQTT_PASSWORD": password,
        "MQTT_TLS_ENABLED": config.get("use_tls", False),
        "MQTT_TLS_CA_CERTS": (
            os.path.join(base_dir, config["ca_cert"])
            if config.get("use_tls") and config.get("ca_cert")
            else None
        ),
    }