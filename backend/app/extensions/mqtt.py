# app/extensions/mqtt.py
import logging
import ssl
from flask_mqtt import Mqtt

mqtt = Mqtt()
logger = logging.getLogger(__name__)

# paho MQTT_ERR_SUCCESS = 0 — returned so flask_mqtt doesn't complain
_MQTT_ERR_SUCCESS = 0


def init_mqtt(app):
    """
    Init Flask-MQTT with non-blocking connect so the app starts even when
    the EMQX broker is temporarily unavailable.

    flask_mqtt calls paho's synchronous client.connect() inside init_app(),
    which raises ConnectionRefusedError when the broker is down.
    We replace connect() with connect_async() before init_app so paho
    queues the connection internally and retries automatically via loop_start().

    TLS: when MQTT_TLS_ENABLED is True but MQTT_TLS_CA_CERTS is None (no local CA
    file), we patch tls_set to skip certificate verification so EMQX Cloud still
    works without distributing the CA cert file.
    """
    # Patch TLS if enabled but no CA cert provided
    if app.config.get("MQTT_TLS_ENABLED") and not app.config.get("MQTT_TLS_CA_CERTS"):
        _original_tls_set = mqtt.client.tls_set

        def _tls_set_no_verify(*args, **kwargs):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            mqtt.client.tls_set_context(ctx)
            logger.warning(
                "MQTT TLS: no CA cert configured — using CERT_NONE (cert verification disabled). "
                "Set 'ca_cert' in broker_config.json for production."
            )

        mqtt.client.tls_set = _tls_set_no_verify

    def _async_connect(host, port=1883, keepalive=60, **kwargs):
        try:
            mqtt.client.connect_async(host, port, keepalive=keepalive)
            mqtt.client.loop_start()
            logger.info("MQTT connecting async to %s:%s (auto-retry enabled)", host, port)
        except Exception as e:
            logger.warning("MQTT async connect failed: %s — will retry when broker is available", e)
        return _MQTT_ERR_SUCCESS  # flask_mqtt checks the return value

    original_connect = mqtt.client.connect
    mqtt.client.connect = _async_connect
    try:
        mqtt.init_app(app)
    finally:
        mqtt.client.connect = original_connect
