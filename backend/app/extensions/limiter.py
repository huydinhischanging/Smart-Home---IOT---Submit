# app/extensions/limiter.py
import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Redis nếu REDIS_URL được set, fallback memory cho dev
_storage_uri = os.environ.get("REDIS_URL", "memory://")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["500 per day", "100 per hour"],
    storage_uri=_storage_uri,
)
