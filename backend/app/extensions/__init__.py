# app/extensions/__init__.py
from .database import db
from .mqtt import mqtt
from .socketio import socketio
from .auth import login_manager, cors

__all__ = [
    "db",
    "mqtt",
    "socketio",
    "login_manager",
    "cors",
]
