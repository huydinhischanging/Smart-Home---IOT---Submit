# app/domain/models/status.py
from dataclasses import dataclass


@dataclass
class DeviceStatus:
    """
    Domain Value Object: Device Status
    """
    device_code: str
    value: str
    is_on: bool
