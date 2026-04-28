import importlib
import sys

import pytest


SETTINGS_MODULE = "app.config.settings"


def _reload_settings_module(monkeypatch, **env):
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    sys.modules.pop(SETTINGS_MODULE, None)
    return importlib.import_module(SETTINGS_MODULE)


def test_settings_dev_requires_explicit_sqlite_opt_in(monkeypatch):
    pass


def test_settings_production_requires_internal_token(monkeypatch):
    with pytest.raises(RuntimeError, match="INTERNAL_TOKEN environment variable is required in production"):
        _reload_settings_module(
            monkeypatch,
            FLASK_ENV="production",
            INTERNAL_TOKEN="",
            DB_PASS="real-db-pass",
            SECRET_KEY="real-secret-key",
        )


def test_settings_production_requires_secret_key(monkeypatch):
    settings = _reload_settings_module(
        monkeypatch,
        FLASK_ENV="production",
        INTERNAL_TOKEN="real-internal-token",
        SECRET_KEY="",
        DATABASE_URL="sqlite:///:memory:",
        DB_PASS="real-db-pass",
    )

    with pytest.raises(RuntimeError, match="SECRET_KEY environment variable is required in production"):
        settings.load_flask_config()


def test_settings_production_rejects_placeholder_db_password(monkeypatch):
    with pytest.raises(RuntimeError, match="DB_PASS is missing or still set to a placeholder"):
        _reload_settings_module(
            monkeypatch,
            FLASK_ENV="production",
            INTERNAL_TOKEN="real-internal-token",
            SECRET_KEY="real-secret-key",
            DB_PASS="replace-with-secure-db-password",
        )