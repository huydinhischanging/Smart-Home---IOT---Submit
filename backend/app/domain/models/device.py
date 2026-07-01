# app/domain/models/device.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class Device:
    """
    Domain Entity: Device
    """
    id: Optional[int]
    code: str
    name: str
    type: str
