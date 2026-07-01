#!/usr/bin/env python3
"""One-shot: create or promote tuhuyne@gmail.com to admin."""
import sys, os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from werkzeug.security import generate_password_hash
from app.config.db_app import create_db_app
from app.extensions.database import db
from app.infrastructure.persistence.models.user_model import UserModel

EMAIL    = "tuhuyne@gmail.com"
USERNAME = "tuhuyne"
PASSWORD = "tuhuyne@gmail.com"
ROLE     = "admin"

app = create_db_app()
with app.app_context():
    user = UserModel.query.filter_by(email=EMAIL).first()
    if user:
        user.role      = ROLE
        user.is_active = True
        user.password  = generate_password_hash(PASSWORD)
        db.session.commit()
        print(f"[OK] Updated existing user → role=admin  ({EMAIL})")
    else:
        user = UserModel(
            username  = USERNAME,
            email     = EMAIL,
            password  = generate_password_hash(PASSWORD),
            role      = ROLE,
            is_active = True,
        )
        db.session.add(user)
        db.session.commit()
        print(f"[OK] Created admin user: {EMAIL} / {PASSWORD}")
