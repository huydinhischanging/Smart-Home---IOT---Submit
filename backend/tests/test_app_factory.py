import logging

import app as app_module


class _Recorder:
    def __init__(self):
        self.calls = []

    def record(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})


class _FakeExtension:
    def __init__(self, recorder):
        self._recorder = recorder

    def init_app(self, app, **kwargs):
        self._recorder.record(app, **kwargs)


class _FakeSocketIO(_FakeExtension):
    def on(self, event_name):
        def decorator(fn):
            self._recorder.record(event_name=event_name, handler=fn.__name__)
            return fn

        return decorator


def _patch_app_factory(monkeypatch, mqtt_enabled):
    db_recorder = _Recorder()
    socketio_recorder = _Recorder()
    login_recorder = _Recorder()
    limiter_recorder = _Recorder()
    mqtt_init_recorder = _Recorder()
    mqtt_listener_recorder = _Recorder()
    scheduler_recorder = _Recorder()
    cors_recorder = _Recorder()

    monkeypatch.setattr(app_module, "load_flask_config", lambda: {
        "SECRET_KEY": "test-secret",
    })
    monkeypatch.setattr(app_module, "load_broker_config", lambda: {
        "MQTT_ENABLED": mqtt_enabled,
        "MQTT_BROKER_URL": "mqtt.example.local",
        "MQTT_BROKER_PORT": 1883,
        "MQTT_USERNAME": "user",
        "MQTT_PASSWORD": "pass",
        "MQTT_TLS_ENABLED": False,
        "MQTT_TLS_CA_CERTS": None,
    })
    monkeypatch.setattr(app_module, "db", _FakeExtension(db_recorder))
    monkeypatch.setattr(app_module, "socketio", _FakeSocketIO(socketio_recorder))
    monkeypatch.setattr(app_module, "login_manager", _FakeExtension(login_recorder))
    monkeypatch.setattr(app_module, "limiter", _FakeExtension(limiter_recorder))
    monkeypatch.setattr(app_module, "init_mqtt", lambda app: mqtt_init_recorder.record(app))
    monkeypatch.setattr(app_module, "init_mqtt_listener", lambda app: mqtt_listener_recorder.record(app))
    monkeypatch.setattr(app_module, "CORS", lambda app, **kwargs: cors_recorder.record(app, **kwargs))

    import app.scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "init_scheduler", lambda app: scheduler_recorder.record(app))

    return {
        "db": db_recorder,
        "socketio": socketio_recorder,
        "login": login_recorder,
        "limiter": limiter_recorder,
        "mqtt_init": mqtt_init_recorder,
        "mqtt_listener": mqtt_listener_recorder,
        "scheduler": scheduler_recorder,
        "cors": cors_recorder,
    }


def test_create_app_skips_mqtt_when_disabled(monkeypatch, caplog):
    recorders = _patch_app_factory(monkeypatch, mqtt_enabled=False)

    with caplog.at_level(logging.INFO):
        flask_app = app_module.create_app()

    assert flask_app.config["MQTT_ENABLED"] is False
    assert len(recorders["mqtt_init"].calls) == 0
    assert len(recorders["mqtt_listener"].calls) == 0
    assert len(recorders["scheduler"].calls) == 1
    assert "MQTT extension initialization skipped because MQTT is disabled." in caplog.text
    assert "MQTT listener initialization skipped because MQTT is disabled." in caplog.text


def test_create_app_initializes_mqtt_when_enabled(monkeypatch):
    recorders = _patch_app_factory(monkeypatch, mqtt_enabled=True)

    flask_app = app_module.create_app()

    assert flask_app.config["MQTT_ENABLED"] is True
    assert len(recorders["db"].calls) == 1
    assert len(recorders["socketio"].calls) >= 1
    assert len(recorders["login"].calls) == 1
    assert len(recorders["limiter"].calls) == 1
    assert len(recorders["cors"].calls) == 1
    assert len(recorders["mqtt_init"].calls) == 1
    assert len(recorders["mqtt_listener"].calls) == 1
    assert len(recorders["scheduler"].calls) == 1


def test_create_app_configures_cors_and_socketio_auth_headers(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://frontend.example,https://admin.example")
    monkeypatch.setenv("SOCKETIO_CORS_ORIGINS", "https://socket.example,https://socket-admin.example")
    recorders = _patch_app_factory(monkeypatch, mqtt_enabled=True)

    app_module.create_app()

    socketio_call = recorders["socketio"].calls[0]
    assert socketio_call["kwargs"]["cors_allowed_origins"] == [
        "https://socket.example",
        "https://socket-admin.example",
    ]

    cors_call = recorders["cors"].calls[0]
    cors_kwargs = cors_call["kwargs"]
    api_resource = cors_kwargs["resources"][r"/api/*"]

    assert cors_kwargs["supports_credentials"] is True
    assert api_resource["origins"] == [
        "https://frontend.example",
        "https://admin.example",
    ]
    assert api_resource["allow_headers"] == [
        "Content-Type",
        "X-INTERNAL-TOKEN",
        "Authorization",
    ]
    assert api_resource["methods"] == ["GET", "POST", "PUT", "DELETE", "OPTIONS"]