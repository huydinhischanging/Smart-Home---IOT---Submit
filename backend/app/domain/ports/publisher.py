# app/domain/ports/publisher.py
from abc import ABC, abstractmethod


class DevicePublisher(ABC):
    """
    Port: publish command / event ra broker (MQTT, AMQP, ...)
    """

    @abstractmethod
    def publish(self, topic: str, payload: str):
        pass
