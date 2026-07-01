"""Tests for map_api — blueprint endpoints (filesystem-based, no database queries)."""
import base64
import json
import os
import tempfile
import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from app.extensions.database import db
from app.infrastructure.persistence.models.user_model import UserModel
from app.presentation.api.auth_api import _make_token
from app.presentation.api.map_api import map_bp, _sanitize_floor_id


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mapapp(tmp_path, monkeypatch):
    """Flask app with map blueprint, using a temp dir for blueprints."""
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    db.init_app(app)
    app.register_blueprint(map_bp)

    # Redirect blueprint storage to tmp_path
    monkeypatch.setattr(
        "app.presentation.api.map_api.BLUEPRINT_BASE",
        str(tmp_path),
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(app, username="mapuser"):
    with app.app_context():
        user = UserModel(
            username=username,
            email=f"{username}@test.com",
            password=generate_password_hash("pass"),
            role="user",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        token = _make_token(user)
        return user.id, token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _small_png_b64():
    """1x1 pixel PNG as base64."""
    return base64.b64encode(
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
        b'\x00\x11\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
    ).decode()


# ---------------------------------------------------------------------------
# _sanitize_floor_id
# ---------------------------------------------------------------------------

class TestSanitizeFloorId:
    def test_allows_alphanumeric(self):
        assert _sanitize_floor_id("floor1") == "floor1"

    def test_strips_path_traversal(self):
        result = _sanitize_floor_id("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_empty_becomes_1(self):
        result = _sanitize_floor_id("!!!")
        assert result == "1"

    def test_truncates_long_id(self):
        result = _sanitize_floor_id("a" * 30)
        assert len(result) == 20

    def test_allows_hyphens_underscores(self):
        assert _sanitize_floor_id("floor-1_A") == "floor-1_A"


# ---------------------------------------------------------------------------
# GET /api/map/floors — empty
# ---------------------------------------------------------------------------

class TestGetFloors:
    def test_returns_empty_list_for_new_user(self, mapapp):
        _, token = _make_user(mapapp)
        client = mapapp.test_client()
        resp = client.get("/api/map/floors", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"] == []

    def test_requires_auth(self, mapapp):
        client = mapapp.test_client()
        resp = client.get("/api/map/floors")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /api/map/blueprint — save blueprint
# ---------------------------------------------------------------------------

class TestSaveBlueprint:
    def test_saves_blueprint_successfully(self, mapapp):
        _, token = _make_user(mapapp, "bp_user")
        client = mapapp.test_client()
        resp = client.post(
            "/api/map/blueprint",
            headers=_auth(token),
            json={
                "floor_id": "1",
                "floor_name": "Ground Floor",
                "image_base64": _small_png_b64(),
                "map_cache": {"device1": {"x": 10, "y": 20}},
                "rooms": ["Living Room"],
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_rejects_empty_image(self, mapapp):
        _, token = _make_user(mapapp, "bp_noimg")
        client = mapapp.test_client()
        resp = client.post(
            "/api/map/blueprint",
            headers=_auth(token),
            json={"floor_id": "1", "image_base64": ""},
        )
        assert resp.status_code == 400

    def test_strips_data_url_prefix(self, mapapp):
        _, token = _make_user(mapapp, "bp_dataurl")
        client = mapapp.test_client()
        image = f"data:image/png;base64,{_small_png_b64()}"
        resp = client.post(
            "/api/map/blueprint",
            headers=_auth(token),
            json={"floor_id": "2", "image_base64": image},
        )
        assert resp.status_code == 200

    def test_floors_list_after_save(self, mapapp):
        _, token = _make_user(mapapp, "bp_list_user")
        client = mapapp.test_client()
        client.post(
            "/api/map/blueprint",
            headers=_auth(token),
            json={"floor_id": "1", "floor_name": "Floor One", "image_base64": _small_png_b64()},
        )
        resp = client.get("/api/map/floors", headers=_auth(token))
        data = resp.get_json()
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "Floor One"
        assert data["data"][0]["has_blueprint"] is True


# ---------------------------------------------------------------------------
# GET /api/map/blueprint/<floor_id>
# ---------------------------------------------------------------------------

class TestGetBlueprint:
    def test_returns_404_when_no_blueprint(self, mapapp):
        _, token = _make_user(mapapp, "getbp_user")
        client = mapapp.test_client()
        resp = client.get("/api/map/blueprint/1", headers=_auth(token))
        assert resp.status_code == 404

    def test_returns_png_after_upload(self, mapapp):
        _, token = _make_user(mapapp, "getbp2_user")
        client = mapapp.test_client()
        client.post(
            "/api/map/blueprint",
            headers=_auth(token),
            json={"floor_id": "1", "image_base64": _small_png_b64()},
        )
        resp = client.get("/api/map/blueprint/1", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.content_type == "image/png"


# ---------------------------------------------------------------------------
# GET + POST /api/map/layout/<floor_id>
# ---------------------------------------------------------------------------

class TestFloorLayout:
    def test_get_layout_returns_empty_for_new_floor(self, mapapp):
        _, token = _make_user(mapapp, "layout_user")
        client = mapapp.test_client()
        resp = client.get("/api/map/layout/1", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["rooms"] == []

    def test_save_layout_then_get(self, mapapp):
        _, token = _make_user(mapapp, "layout2_user")
        client = mapapp.test_client()
        client.post(
            "/api/map/layout/1",
            headers=_auth(token),
            json={
                "rooms": [
                    {"name": "Room A", "points": [{"x": 0, "y": 0}]},
                    {"name": "Room B", "points": [{"x": 1, "y": 1}]},
                ],
                "map_cache": {"d1": {"x": 5, "y": 5}},
            },
        )
        resp = client.get("/api/map/layout/1", headers=_auth(token))
        data = resp.get_json()
        room_names = [r.get("name") for r in data["data"]["rooms"] if isinstance(r, dict)]
        assert "Room A" in room_names
        assert "d1" in data["data"]["map_cache"]


# ---------------------------------------------------------------------------
# POST /api/map/floor — create new floor
# ---------------------------------------------------------------------------

class TestCreateFloor:
    def test_creates_floor_with_name(self, mapapp):
        _, token = _make_user(mapapp, "newfloor_user")
        client = mapapp.test_client()
        resp = client.post(
            "/api/map/floor",
            headers=_auth(token),
            json={"name": "Second Floor"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["name"] == "Second Floor"

    def test_sequential_ids_assigned(self, mapapp):
        _, token = _make_user(mapapp, "seq_user")
        client = mapapp.test_client()
        r1 = client.post("/api/map/floor", headers=_auth(token), json={"name": "F1"})
        r2 = client.post("/api/map/floor", headers=_auth(token), json={"name": "F2"})
        id1 = int(r1.get_json()["data"]["id"])
        id2 = int(r2.get_json()["data"]["id"])
        assert id2 == id1 + 1


# ---------------------------------------------------------------------------
# DELETE /api/map/floor/<floor_id>
# ---------------------------------------------------------------------------

class TestDeleteFloor:
    def test_delete_floor_removes_it(self, mapapp):
        _, token = _make_user(mapapp, "del_floor_user")
        client = mapapp.test_client()
        r1 = client.post("/api/map/floor", headers=_auth(token), json={"name": "Del Me"})
        r2 = client.post("/api/map/floor", headers=_auth(token), json={"name": "Keep Me"})
        fid = r1.get_json()["data"]["id"]

        resp = client.delete(f"/api/map/floor/{fid}", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_cannot_delete_last_floor(self, mapapp):
        _, token = _make_user(mapapp, "last_floor_user")
        client = mapapp.test_client()
        r1 = client.post("/api/map/floor", headers=_auth(token), json={"name": "Only Floor"})
        fid = r1.get_json()["data"]["id"]

        resp = client.delete(f"/api/map/floor/{fid}", headers=_auth(token))
        assert resp.status_code == 400

    def test_delete_nonexistent_floor_returns_404(self, mapapp):
        _, token = _make_user(mapapp, "del_nonexistent_user")
        client = mapapp.test_client()
        resp = client.delete("/api/map/floor/999", headers=_auth(token))
        assert resp.status_code == 404
