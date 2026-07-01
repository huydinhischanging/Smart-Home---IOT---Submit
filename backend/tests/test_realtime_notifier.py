"""Tests for RealtimeNotifier — covers all emit methods."""
from unittest.mock import MagicMock, call

import pytest

from app.usecases.realtime_notifier import RealtimeNotifier


def _make_notifier():
    emitter = MagicMock()
    return RealtimeNotifier(socket_emitter=emitter), emitter


class TestRealtimeNotifier:
    def test_notify_device_status_with_user(self):
        notifier, emitter = _make_notifier()
        notifier.notify_device_status({"code": "fan", "status": "on"}, user_id=5)
        emitter.emit.assert_called_once_with("device_status", {"code": "fan", "status": "on"}, room="user_5")

    def test_notify_device_status_no_user(self):
        notifier, emitter = _make_notifier()
        notifier.notify_device_status({"code": "fan"})
        emitter.emit.assert_called_once_with("device_status", {"code": "fan"}, room=None)

    def test_notify_device_list_changed_with_user(self):
        notifier, emitter = _make_notifier()
        notifier.notify_device_list_changed(user_id=3)
        emitter.emit.assert_called_once_with("device_list_changed", {}, room="user_3")

    def test_notify_device_list_changed_no_user(self):
        notifier, emitter = _make_notifier()
        notifier.notify_device_list_changed()
        emitter.emit.assert_called_once_with("device_list_changed", {}, room=None)

    def test_notify_alert_with_user(self):
        notifier, emitter = _make_notifier()
        payload = {"message": "SOS", "level": "critical"}
        notifier.notify_alert(payload, user_id=7)
        emitter.emit.assert_called_once_with("alert", payload, room="user_7")

    def test_notify_alert_no_user(self):
        notifier, emitter = _make_notifier()
        notifier.notify_alert({"message": "test"})
        emitter.emit.assert_called_once_with("alert", {"message": "test"}, room=None)

    def test_notify_ai_mood_with_user(self):
        notifier, emitter = _make_notifier()
        payload = {"mood": "calm"}
        notifier.notify_ai_mood(payload, user_id=2)
        emitter.emit.assert_called_once_with("ai_mood", payload, room="user_2")

    def test_notify_ai_advice_with_user(self):
        notifier, emitter = _make_notifier()
        payload = {"advice": "rest"}
        notifier.notify_ai_advice(payload, user_id=1)
        emitter.emit.assert_called_once_with("ai_advice", payload, room="user_1")

    def test_notify_ai_explain_with_user(self):
        notifier, emitter = _make_notifier()
        payload = {"explain": "heart rate elevated"}
        notifier.notify_ai_explain(payload, user_id=4)
        emitter.emit.assert_called_once_with("ai_explain", payload, room="user_4")

    def test_room_with_user_id(self):
        assert RealtimeNotifier._room(10) == "user_10"

    def test_room_without_user_id(self):
        assert RealtimeNotifier._room(None) is None

    def test_room_zero_user_id(self):
        # user_id=0 is technically valid — _room returns "user_0", not None
        assert RealtimeNotifier._room(0) == "user_0"

    def test_emit_called_for_every_method(self):
        notifier, emitter = _make_notifier()
        notifier.notify_device_status({}, user_id=1)
        notifier.notify_device_list_changed(user_id=1)
        notifier.notify_alert({}, user_id=1)
        notifier.notify_ai_mood({}, user_id=1)
        notifier.notify_ai_advice({}, user_id=1)
        notifier.notify_ai_explain({}, user_id=1)
        assert emitter.emit.call_count == 6
