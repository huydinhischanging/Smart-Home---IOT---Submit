"""Tests for Room API — list, create, delete with multi-tenant isolation."""
import pytest
from flask import Flask

from app.extensions.database import db
from app.extensions.limiter import limiter
from app.presentation.api.auth_api import auth_api
from app.presentation.api.room_api import room_api
from app.usecases.room_usecase import RoomUseCase
from app.wiring import container


# ──────────────────────────────────────────────
# App fixture
# ──────────────────────────────────────────────

@pytest.fixture()
def app(monkeypatch):
    a = Flask(__name__)
    a.config.update(
        SECRET_KEY="room-test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
        RATELIMIT_ENABLED=False,
    )
    db.init_app(a)
    limiter.init_app(a)
    a.register_blueprint(auth_api, url_prefix="/api/auth")
    a.register_blueprint(room_api, url_prefix="/api/rooms")

    room_uc = RoomUseCase()
    monkeypatch.setattr(container, "room_usecase", lambda: room_uc)

    with a.app_context():
        db.create_all()

    return a


@pytest.fixture()
def client(app):
    return app.test_client()


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _register_and_token(client, username="user1", email="user1@example.com"):
    client.post("/api/auth/register", json={
        "username": username, "email": email, "password": "Password1"
    })
    r = client.post("/api/auth/login", json={"identity": email, "password": "Password1"})
    return r.get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ──────────────────────────────────────────────
# List rooms
# ──────────────────────────────────────────────

def test_list_rooms_empty(client):
    token = _register_and_token(client)
    r = client.get("/api/rooms", headers=_auth(token))
    assert r.status_code == 200
    assert r.get_json()["data"] == []


def test_list_rooms_requires_auth(client):
    r = client.get("/api/rooms")
    assert r.status_code == 401


# ──────────────────────────────────────────────
# Create room
# ──────────────────────────────────────────────

def test_create_room(client):
    token = _register_and_token(client)
    r = client.post("/api/rooms", json={"name": "Living Room"}, headers=_auth(token))
    assert r.status_code == 201
    assert r.get_json()["success"] is True


def test_create_room_missing_name(client):
    token = _register_and_token(client)
    r = client.post("/api/rooms", json={"name": ""}, headers=_auth(token))
    assert r.status_code == 400


def test_create_room_name_too_long(client):
    token = _register_and_token(client)
    r = client.post("/api/rooms", json={"name": "R" * 101}, headers=_auth(token))
    assert r.status_code == 400


def test_create_room_no_body(client):
    token = _register_and_token(client)
    r = client.post("/api/rooms", headers=_auth(token), content_type="application/json")
    assert r.status_code == 400


def test_create_room_requires_auth(client):
    r = client.post("/api/rooms", json={"name": "Bedroom"})
    assert r.status_code == 401


def test_create_room_appears_in_list(client):
    token = _register_and_token(client)
    client.post("/api/rooms", json={"name": "Bedroom"}, headers=_auth(token))
    r = client.get("/api/rooms", headers=_auth(token))
    names = [room["name"] for room in r.get_json()["data"]]
    assert "Bedroom" in names


def test_create_duplicate_room_returns_existing(client):
    token = _register_and_token(client)
    r1 = client.post("/api/rooms", json={"name": "Kitchen"}, headers=_auth(token))
    r2 = client.post("/api/rooms", json={"name": "Kitchen"}, headers=_auth(token))
    # Both succeed, second returns existed=True
    assert r1.get_json()["success"] is True
    assert r2.get_json()["success"] is True
    # Only one room in list
    r_list = client.get("/api/rooms", headers=_auth(token))
    assert len(r_list.get_json()["data"]) == 1


# ──────────────────────────────────────────────
# Delete room
# ──────────────────────────────────────────────

def test_delete_room(client):
    token = _register_and_token(client)
    r_create = client.post("/api/rooms", json={"name": "Bathroom"}, headers=_auth(token))
    room_id = r_create.get_json()["room_id"]

    r_del = client.delete(f"/api/rooms/{room_id}", headers=_auth(token))
    assert r_del.status_code == 200
    assert r_del.get_json()["success"] is True

    r_list = client.get("/api/rooms", headers=_auth(token))
    assert r_list.get_json()["data"] == []


def test_delete_nonexistent_room_returns_404(client):
    token = _register_and_token(client)
    r = client.delete("/api/rooms/9999", headers=_auth(token))
    assert r.status_code == 404


def test_delete_room_requires_auth(client):
    r = client.delete("/api/rooms/1")
    assert r.status_code == 401


# ──────────────────────────────────────────────
# Multi-tenant isolation
# ──────────────────────────────────────────────

def test_rooms_isolated_between_users(client):
    token_a = _register_and_token(client, "alice", "alice@example.com")
    token_b = _register_and_token(client, "bob", "bob@example.com")

    client.post("/api/rooms", json={"name": "Alice Room"}, headers=_auth(token_a))

    r = client.get("/api/rooms", headers=_auth(token_b))
    names = [room["name"] for room in r.get_json()["data"]]
    assert "Alice Room" not in names


def test_cannot_delete_other_users_room(client):
    token_a = _register_and_token(client, "alice2", "alice2@example.com")
    token_b = _register_and_token(client, "bob2", "bob2@example.com")

    r_create = client.post("/api/rooms", json={"name": "Alice's Room"}, headers=_auth(token_a))
    room_id = r_create.get_json()["room_id"]

    r_del = client.delete(f"/api/rooms/{room_id}", headers=_auth(token_b))
    assert r_del.status_code == 404
