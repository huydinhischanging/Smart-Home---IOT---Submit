# app/config/__init__.py
# Re-export INTERNAL_TOKEN from the single source of truth (settings.py)
from app.config.settings import INTERNAL_TOKEN  # noqa: F401
