from flask import Flask

from app.config.settings import load_flask_config
from app.extensions.database import db
from app.infrastructure.persistence import models as _models  # noqa: F401


def create_db_app() -> Flask:
    app = Flask(__name__)
    app.config.update(load_flask_config())
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    db.init_app(app)
    return app