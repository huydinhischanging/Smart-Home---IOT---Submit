# ==========================================================
# FILE: run.py
# IOT CONTROL CENTER – THREADING VERSION
# ==========================================================
import os
import logging

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ENV_FILE_PATH = os.path.join(BASE_DIR, ".env")

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(dotenv_path=ENV_FILE_PATH)  # Load backend/.env from a stable path
else:
    print("[WARN] python-dotenv not installed; skipping .env loading.")

# ----------------------------------------------------------
# Configure structured logging before anything else
# ----------------------------------------------------------
_log_level = logging.DEBUG if os.environ.get("FLASK_DEBUG") == "1" else logging.INFO
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

from app import create_app
from app.extensions.socketio import socketio

# ==========================================================
# FORCE WORKING DIR = BACKEND ROOT
# ==========================================================
os.chdir(BASE_DIR)
logger.info("BACKEND DIR: %s", BASE_DIR)

# ==========================================================
# CREATE FLASK APP
# ==========================================================
app = create_app()

# ==========================================================
# MAIN ENTRY
# ==========================================================
if __name__ == "__main__":
    port = 5000
    host = "0.0.0.0"
    logger.info("=" * 60)
    logger.info("IOT CONTROL CENTER – SERVER RUNNING")
    logger.info("Backend API : http://127.0.0.1:%d (local machine)", port)
    logger.info("Backend API : http://<your-lan-ip>:%d (phone/tablet)", port)
    logger.info("Socket.IO   : ws://<your-lan-ip>:%d/socket.io", port)
    logger.info("=" * 60)
    try:
        socketio.run(
            app,
            host=host,
            port=port,
            debug=os.environ.get("FLASK_DEBUG", "0") == "1",
            use_reloader=False,
            allow_unsafe_werkzeug=False
        )
    except KeyboardInterrupt:
        logger.info("Server stopped.")
        import sys
        sys.exit(0)