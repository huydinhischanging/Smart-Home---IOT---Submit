# app/usecases/config_usecase.py
import os


class ConfigUseCase:
    """
    Application logic
    Quản lý cấu hình MQTT broker
    """

    DEFAULT_CONFIG = {
        "url":      os.environ.get("MQTT_URL", "b2652cf8.ala.us-east-1.emqxsl.com"),
        "port":     int(os.environ.get("MQTT_PORT", "8883")),
        "username": os.environ.get("MQTT_USERNAME", ""),
        "password": os.environ.get("MQTT_PASSWORD", ""),
        "use_tls":  os.environ.get("MQTT_USE_TLS", "true").lower() in {"1", "true", "yes"},
        "ca_cert":  "emqxsl-ca.crt",
    }

    REQUIRED_KEYS = {"url", "port"}

    def __init__(self, config_repo):
        self.config_repo = config_repo

    def load(self) -> dict:
        config = self.config_repo.load()

        if not config:
            return self.DEFAULT_CONFIG.copy()

        if not self.REQUIRED_KEYS.issubset(config.keys()):
            return self.DEFAULT_CONFIG.copy()

        return {**self.DEFAULT_CONFIG, **config}

    def save(self, data: dict) -> bool:
        return self.config_repo.save(data)
