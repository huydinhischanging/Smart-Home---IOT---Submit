#app/config/settings.py
import os
import ssl
import logging
import secrets

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from app.usecases.config_usecase import ConfigUseCase
from app.infrastructure.config.file_config_repo import FileConfigRepository

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../..")
)
ENV_FILE_PATH = os.path.join(BACKEND_DIR, ".env")

if load_dotenv is not None:
    load_dotenv(dotenv_path=ENV_FILE_PATH)

# ======================================================
# ENVIRONMENT
# ======================================================
_FLASK_ENV = os.environ.get("FLASK_ENV", "development")
_IS_PRODUCTION = _FLASK_ENV == "production"

CA_CERT_PATH = os.path.join(BACKEND_DIR, "emqxsl-ca.crt")
logger.debug("BACKEND DIR: %s", BACKEND_DIR)

_PLACEHOLDER_VALUES = {
    "",
    "YOUR_SECURE_PASSWORD_HERE",
    "YOUR_SECRET_KEY_HERE_GENERATE_RANDOM",
    "YOUR_INTERNAL_TOKEN_HERE",
    "YOUR_GEMINI_API_KEY_HERE",
    "replace-with-secure-db-password",
    "replace-with-a-strong-random-key",
    "replace-with-a-strong-random-token",
}


def _is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    return str(value).strip() in _PLACEHOLDER_VALUES


def _truthy_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# ======================================================
# INTERNAL AUTH (API <-> GUI)
# ======================================================
_raw_internal_token = os.environ.get("INTERNAL_TOKEN")
if _is_placeholder(_raw_internal_token):
    if _IS_PRODUCTION:
        raise RuntimeError("❌ INTERNAL_TOKEN environment variable is required in production!")
    logger.warning("⚠️  INTERNAL_TOKEN not set — generating ephemeral development token")
    _raw_internal_token = secrets.token_urlsafe(32)
INTERNAL_TOKEN: str = _raw_internal_token

# ======================================================
# DATABASE CONFIG — set via .env
# ======================================================
DB_USER = os.environ.get("DB_USER", "iot_user")
_raw_db_pass = os.environ.get("DB_PASS")
if _IS_PRODUCTION and _is_placeholder(_raw_db_pass):
    raise RuntimeError(
        "❌ DB_PASS is missing or still set to a placeholder in backend/.env. "
        "Update backend/.env with the real MySQL password for DB_USER before starting the server."
    )
DB_PASS: str = _raw_db_pass or ""
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_NAME = os.environ.get("DB_NAME", "iot_smarthome")

def _build_database_uri() -> str:
    explicit_uri = os.environ.get("DATABASE_URL")
    if explicit_uri:
        logger.info("Using DATABASE_URL from environment")
        return explicit_uri
    if _is_placeholder(_raw_db_pass):
        if _IS_PRODUCTION:
            raise RuntimeError(
                "❌ DB_PASS is missing or still set to a placeholder in backend/.env. "
                "Production requires a real MySQL password or DATABASE_URL."
            )
        raise RuntimeError(
            "❌ DB_PASS is missing or still set to a placeholder in backend/.env. "
            "Development requires a real MySQL password or DATABASE_URL."
        )
    logger.info("Using MySQL database at %s:%s/%s", DB_HOST, DB_PORT, DB_NAME)
    return f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# ======================================================
# FLASK CONFIG LOADER
# ======================================================
def load_flask_config():
    # --------------------------------------------------
    # LOAD MQTT CONFIG FROM config.json
    # --------------------------------------------------
    repo = FileConfigRepository(BACKEND_DIR)
    usecase = ConfigUseCase(repo)
    broker = usecase.load()

    # --------------------------------------------------
    # SECRET KEY
    # --------------------------------------------------
    _secret_key = os.environ.get("SECRET_KEY")
    if _is_placeholder(_secret_key):
        if _IS_PRODUCTION:
            raise RuntimeError("❌ SECRET_KEY environment variable is required in production!")
        logger.warning(
            "⚠️  SECRET_KEY not set — generating ephemeral key. "
            "Sessions will NOT persist across restarts!"
        )
        _secret_key = secrets.token_urlsafe(32)

    # --------------------------------------------------
    # DATABASE URI
    # --------------------------------------------------
    DATABASE_URI = _build_database_uri()

    return {
        # --------------------------------------------------
        # Flask
        # --------------------------------------------------
        "SECRET_KEY": _secret_key,

        # --------------------------------------------------
        # Database
        # --------------------------------------------------
        "SQLALCHEMY_DATABASE_URI": DATABASE_URI,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "ALLOW_PASSWORD_RESET_TOKEN_FALLBACK": _truthy_env(
            "ALLOW_PASSWORD_RESET_TOKEN_FALLBACK",
            default=False,
        ),
        "PASSWORD_RESET_TOKEN_TTL_SEC": int(
            os.environ.get("PASSWORD_RESET_TOKEN_TTL_SEC", "1800")
        ),

        # --------------------------------------------------
        # MQTT
        # --------------------------------------------------
        "MQTT_BROKER_URL":    broker["url"],
        "MQTT_BROKER_PORT":   broker["port"],
        "MQTT_USERNAME":      broker.get("username"),
        "MQTT_PASSWORD":      broker.get("password"),
        "MQTT_TLS_ENABLED":   broker.get("use_tls", False),
        "MQTT_TLS_CA_CERTS": (
            CA_CERT_PATH
            if broker.get("use_tls") and os.path.exists(CA_CERT_PATH)
            else None
        ),
        "MQTT_TLS_VERSION": ssl.PROTOCOL_TLS_CLIENT,
        "MQTT_VERBOSE_SENSOR_LOG": _truthy_env(
            "MQTT_VERBOSE_SENSOR_LOG",
            default=False,
        ),
        "MQTT_DEBUG_LOG": _truthy_env(
            "MQTT_DEBUG_LOG",
            default=False,
        ),

        # --------------------------------------------------
        # SocketIO
        # --------------------------------------------------
        "SOCKETIO_CORS_ALLOWED_ORIGINS": "*",
    }