# wsgi.py — Entry point cho Gunicorn / production WSGI server
# Dùng: gunicorn --worker-class eventlet -w 1 wsgi:application
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ENV_FILE_PATH = os.path.join(BASE_DIR, ".env")

if os.path.exists(ENV_FILE_PATH):
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=ENV_FILE_PATH)
    except ImportError:
        pass

from app import create_app
from app.extensions.socketio import socketio

application = create_app()

if __name__ == "__main__":
    socketio.run(application)
