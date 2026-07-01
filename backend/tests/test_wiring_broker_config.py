import logging

from app import wiring


class _FakeConfigUseCase:
    def __init__(self, repo, config):
        self._config = config

    def load(self):
        return self._config


def _patch_broker_config(monkeypatch, config):
    monkeypatch.setattr(
        wiring,
        "ConfigUseCase",
        lambda repo: _FakeConfigUseCase(repo, config),
    )


def test_load_broker_config_uses_env_overrides_and_enables_mqtt(monkeypatch):
    _patch_broker_config(
        monkeypatch,
        {
            "url": "placeholder.example",
            "port": 1883,
            "username": "placeholder-user",
            "password": "placeholder-pass",
            "use_tls": True,
            "ca_cert": "emqxsl-ca.crt",
        },
    )
    monkeypatch.setenv("MQTT_URL", "mqtt.example.local")
    monkeypatch.setenv("MQTT_PORT", "2883")
    monkeypatch.setenv("MQTT_USERNAME", "real-user")
    monkeypatch.setenv("MQTT_PASSWORD", "real-pass")
    monkeypatch.delenv("MQTT_ENABLED", raising=False)

    config = wiring.load_broker_config()

    assert config["MQTT_ENABLED"] is True
    assert config["MQTT_BROKER_URL"] == "mqtt.example.local"
    assert config["MQTT_BROKER_PORT"] == 2883
    assert config["MQTT_USERNAME"] == "real-user"
    assert config["MQTT_PASSWORD"] == "real-pass"
    assert config["MQTT_TLS_ENABLED"] is True
    assert config["MQTT_TLS_CA_CERTS"].endswith("emqxsl-ca.crt")


def test_load_broker_config_explicit_disable_wins_over_valid_credentials(monkeypatch):
    _patch_broker_config(
        monkeypatch,
        {
            "url": "mqtt.example.local",
            "port": 1883,
            "username": "real-user",
            "password": "real-pass",
            "use_tls": False,
            "ca_cert": None,
        },
    )
    monkeypatch.setenv("MQTT_ENABLED", "false")

    config = wiring.load_broker_config()

    assert config["MQTT_ENABLED"] is False
    assert config["MQTT_TLS_ENABLED"] is False
    assert config["MQTT_TLS_CA_CERTS"] is None


def test_load_broker_config_disables_placeholder_credentials_and_logs_warning(monkeypatch, caplog):
    _patch_broker_config(
        monkeypatch,
        {
            "url": "your-broker-url-here.emqxsl.com",
            "port": 8883,
            "username": "your-mqtt-username",
            "password": "your-mqtt-password",
            "use_tls": True,
            "ca_cert": "emqxsl-ca.crt",
        },
    )
    monkeypatch.delenv("MQTT_URL", raising=False)
    monkeypatch.delenv("MQTT_PORT", raising=False)
    monkeypatch.delenv("MQTT_USERNAME", raising=False)
    monkeypatch.delenv("MQTT_PASSWORD", raising=False)
    monkeypatch.delenv("MQTT_ENABLED", raising=False)

    with caplog.at_level(logging.WARNING):
        config = wiring.load_broker_config()

    assert config["MQTT_ENABLED"] is False
    assert "MQTT credentials are missing or placeholder values" in caplog.text