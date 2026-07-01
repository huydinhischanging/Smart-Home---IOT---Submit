"""Tests for RoomUseCase — create, update_color, get_all, delete."""
import pytest
from flask import Flask

from app.extensions.database import db
from app.infrastructure.persistence.models.rooms_model import RoomModel
from app.usecases.room_usecase import RoomUseCase


def _make_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    db.init_app(app)
    return app


@pytest.fixture
def app_ctx():
    app = _make_app()
    with app.app_context():
        db.create_all()
        yield app
    # teardown: nothing needed — in-memory DB is dropped automatically


@pytest.fixture
def usecase():
    return RoomUseCase()


# ---------------------------------------------------------------------------
# create_room
# ---------------------------------------------------------------------------

class TestCreateRoom:
    def test_creates_new_room(self, app_ctx, usecase):
        result = usecase.create_room({"name": "Living Room"}, user_id=1)
        assert result["success"] is True
        assert "room_id" in result

    def test_empty_name_fails(self, app_ctx, usecase):
        result = usecase.create_room({"name": ""}, user_id=1)
        assert result["success"] is False
        assert "required" in result["message"].lower()

    def test_missing_name_fails(self, app_ctx, usecase):
        result = usecase.create_room({}, user_id=1)
        assert result["success"] is False

    def test_duplicate_name_returns_existing(self, app_ctx, usecase):
        usecase.create_room({"name": "Kitchen"}, user_id=1)
        result = usecase.create_room({"name": "Kitchen"}, user_id=1)
        assert result["success"] is True
        assert result.get("existed") is True

    def test_duplicate_with_new_color_updates_color(self, app_ctx, usecase):
        usecase.create_room({"name": "Bedroom", "color": "red"}, user_id=1)
        result = usecase.create_room({"name": "Bedroom", "color": "blue"}, user_id=1)
        assert result["success"] is True
        room = db.session.get(RoomModel, result["room_id"])
        assert room.color == "blue"

    def test_custom_color_saved(self, app_ctx, usecase):
        result = usecase.create_room({"name": "Garage", "color": "rgba(255,0,0,0.5)"}, user_id=1)
        room = db.session.get(RoomModel, result["room_id"])
        assert room.color == "rgba(255,0,0,0.5)"

    def test_points_saved(self, app_ctx, usecase):
        points = [{"x": 0, "y": 0}, {"x": 10, "y": 0}]
        result = usecase.create_room({"name": "Hall", "points": points}, user_id=1)
        room = db.session.get(RoomModel, result["room_id"])
        assert room.polygon_data == points

    def test_rooms_are_isolated_per_user(self, app_ctx, usecase):
        usecase.create_room({"name": "Office"}, user_id=1)
        usecase.create_room({"name": "Office"}, user_id=2)
        rooms_u1 = usecase.get_all_rooms(user_id=1)
        rooms_u2 = usecase.get_all_rooms(user_id=2)
        assert len(rooms_u1) == 1
        assert len(rooms_u2) == 1


# ---------------------------------------------------------------------------
# update_room_color
# ---------------------------------------------------------------------------

class TestUpdateRoomColor:
    def test_update_color_success(self, app_ctx, usecase):
        create_result = usecase.create_room({"name": "Dining"}, user_id=1)
        room_id = create_result["room_id"]
        result = usecase.update_room_color(room_id, "green")
        assert result["success"] is True
        room = db.session.get(RoomModel, room_id)
        assert room.color == "green"

    def test_update_nonexistent_room(self, app_ctx, usecase):
        result = usecase.update_room_color(99999, "red")
        assert result["success"] is False
        assert "not found" in result["message"].lower()


# ---------------------------------------------------------------------------
# get_all_rooms
# ---------------------------------------------------------------------------

class TestGetAllRooms:
    def test_returns_empty_list_for_new_user(self, app_ctx, usecase):
        result = usecase.get_all_rooms(user_id=999)
        assert result == []

    def test_returns_all_rooms_for_user(self, app_ctx, usecase):
        usecase.create_room({"name": "R1"}, user_id=5)
        usecase.create_room({"name": "R2"}, user_id=5)
        result = usecase.get_all_rooms(user_id=5)
        assert len(result) == 2

    def test_room_has_expected_fields(self, app_ctx, usecase):
        usecase.create_room({"name": "Study"}, user_id=3)
        rooms = usecase.get_all_rooms(user_id=3)
        assert rooms[0]["name"] == "Study"
        assert "id" in rooms[0]
        assert "color" in rooms[0]
        assert "points" in rooms[0]
        assert "device_count" in rooms[0]

    def test_returns_all_rooms_when_no_user_filter(self, app_ctx, usecase):
        usecase.create_room({"name": "Shared1"}, user_id=10)
        usecase.create_room({"name": "Shared2"}, user_id=11)
        result = usecase.get_all_rooms()
        assert len(result) >= 2


# ---------------------------------------------------------------------------
# delete_room
# ---------------------------------------------------------------------------

class TestDeleteRoom:
    def test_delete_existing_room(self, app_ctx, usecase):
        result = usecase.create_room({"name": "Temp Room"}, user_id=1)
        room_id = result["room_id"]
        delete_result = usecase.delete_room(room_id, user_id=1)
        assert delete_result["success"] is True

    def test_delete_nonexistent_room(self, app_ctx, usecase):
        result = usecase.delete_room(99999, user_id=1)
        assert result["success"] is False
        assert "not found" in result["message"].lower()

    def test_delete_removes_room_from_list(self, app_ctx, usecase):
        result = usecase.create_room({"name": "Porch"}, user_id=1)
        room_id = result["room_id"]
        usecase.delete_room(room_id, user_id=1)
        rooms = usecase.get_all_rooms(user_id=1)
        assert all(r["id"] != room_id for r in rooms)

    def test_delete_wrong_user_fails(self, app_ctx, usecase):
        result = usecase.create_room({"name": "Private Room"}, user_id=42)
        room_id = result["room_id"]
        delete_result = usecase.delete_room(room_id, user_id=99)
        assert delete_result["success"] is False
