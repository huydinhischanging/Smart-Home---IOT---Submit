# app/ports/realtime.py
from abc import ABC, abstractmethod


class RealtimeEmitter(ABC):
    """
    Port: phát realtime event ra ngoài (Socket / Unity / ...)
    """

    @abstractmethod
    def emit_device_status(self, device_name: str, payload: str):
        pass
