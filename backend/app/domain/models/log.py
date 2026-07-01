# app/domain/models/log.py
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ControlLog:
    """
    Domain Entity: Control Log
    """
    device_code: str
    action: str
    source: str
    created_at: datetime
