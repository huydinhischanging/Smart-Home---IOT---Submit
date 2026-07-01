# app/gateways/mqtt_publisher.py
import logging
from app.extensions.mqtt import mqtt

logger = logging.getLogger(__name__)


class MqttPublisher:
    """
    OUTPUT Gateway
    Publish command ra MQTT broker (ESP / IoT devices)
    """

    def send_device_command(self, device_code: str, payload: str) -> bool:
        topic = f"home/control/{device_code}"
        logger.debug("[MQTT -> DEVICE] %s -> %s", topic, payload)
        try:
            publish_result = mqtt.publish(topic, payload)

            # flask_mqtt may return bool, tuple(result, mid), or paho MQTTMessageInfo.
            if isinstance(publish_result, bool):
                ok = publish_result
            elif isinstance(publish_result, tuple) and publish_result:
                ok = publish_result[0] == 0
            elif hasattr(publish_result, "rc"):
                ok = int(getattr(publish_result, "rc", 1)) == 0
            else:
                ok = True

            if not ok:
                logger.error("[MQTT ERROR] Publish rejected for %s", topic)
            return ok
        except Exception as e:
            logger.error("[MQTT ERROR] Failed to publish to %s: %s", topic, e)
            return False
