"""Tests for SocketEmitter and MqttPublisher gateways."""
from unittest.mock import MagicMock, patch, call
import pytest

from app.gateways.socket_emitter import SocketEmitter
from app.gateways.mqtt_publisher import MqttPublisher


# ==========================================
# SocketEmitter Tests
# ==========================================

class TestSocketEmitter:
    """Test the SocketEmitter gateway for real-time event broadcasting."""

    @pytest.fixture
    def mock_socketio(self):
        """Provide a mocked socketio instance."""
        return MagicMock()

    @pytest.fixture
    def emitter(self, mock_socketio):
        """Create a SocketEmitter with mocked socketio."""
        with patch("app.extensions.socketio.socketio", mock_socketio):
            emitter = SocketEmitter()
            emitter.socketio = mock_socketio
            return emitter

    def test_emit_without_room(self, emitter):
        """Test emitting an event without specifying a room."""
        emitter.emit("device_status", {"code": "fan", "status": "on"})
        emitter.socketio.emit.assert_called_once_with("device_status", {"code": "fan", "status": "on"})

    def test_emit_with_room(self, emitter):
        """Test emitting an event to a specific room."""
        emitter.emit("alert", {"message": "SOS"}, room="user_5")
        emitter.socketio.emit.assert_called_once_with("alert", {"message": "SOS"}, room="user_5")

    def test_emit_empty_payload(self, emitter):
        """Test emitting with empty payload."""
        emitter.emit("device_list_changed", {})
        emitter.socketio.emit.assert_called_once_with("device_list_changed", {})

    def test_emit_complex_payload(self, emitter):
        """Test emitting with complex nested data."""
        payload = {
            "device": {
                "id": 1,
                "name": "Living Room Fan",
                "status": "on"
            },
            "timestamp": "2026-04-19T10:30:00Z"
        }
        emitter.emit("device_updated", payload, room="user_1")
        emitter.socketio.emit.assert_called_once_with("device_updated", payload, room="user_1")

    def test_emit_handles_socket_error(self, emitter):
        """Test that emit gracefully handles socketio errors."""
        emitter.socketio.emit.side_effect = Exception("Socket connection lost")
        # Should not raise, just log error
        emitter.emit("device_status", {"code": "fan"})
        # Verify the attempted emit was made
        emitter.socketio.emit.assert_called_once()

    def test_emit_device_status_backward_compat(self, emitter):
        """Test backward compatibility method emit_device_status."""
        emitter.emit_device_status("fan", "on")
        emitter.socketio.emit.assert_called_once_with(
            "device_status",
            {"device_name": "fan", "payload": "on"}
        )

    def test_emit_device_list_changed_backward_compat(self, emitter):
        """Test backward compatibility method emit_device_list_changed."""
        emitter.emit_device_list_changed()
        emitter.socketio.emit.assert_called_once_with("device_list_changed", {})

    def test_multiple_emits_in_sequence(self, emitter):
        """Test sending multiple events in sequence."""
        emitter.emit("event1", {"data": "a"})
        emitter.emit("event2", {"data": "b"}, room="user_1")
        emitter.emit("event3", {})

        assert emitter.socketio.emit.call_count == 3
        calls = emitter.socketio.emit.call_args_list
        assert calls[0] == call("event1", {"data": "a"})
        assert calls[1] == call("event2", {"data": "b"}, room="user_1")
        assert calls[2] == call("event3", {})


# ==========================================
# MqttPublisher Tests
# ==========================================

class TestMqttPublisher:
    """Test the MqttPublisher gateway for IoT device communication."""

    def test_send_device_command_success(self):
        """Test successfully sending a command to a device."""
        mock_mqtt = MagicMock()
        mock_mqtt.publish.return_value = True
        with patch("app.gateways.mqtt_publisher.mqtt", mock_mqtt):
            publisher = MqttPublisher()
            result = publisher.send_device_command("fan", "on")
            assert result is True
            mock_mqtt.publish.assert_called_once_with("home/control/fan", "on")

    def test_send_device_command_with_json(self):
        """Test sending a JSON payload to a device."""
        mock_mqtt = MagicMock()
        mock_mqtt.publish.return_value = True
        with patch("app.gateways.mqtt_publisher.mqtt", mock_mqtt):
            publisher = MqttPublisher()
            payload = '{"action": "set_temp", "value": 25}'
            result = publisher.send_device_command("ac", payload)
            assert result is True
            mock_mqtt.publish.assert_called_once_with("home/control/ac", payload)

    def test_send_device_command_failure(self):
        """Test handling of MQTT publish failure."""
        mock_mqtt = MagicMock()
        mock_mqtt.publish.side_effect = Exception("Connection lost")
        with patch("app.gateways.mqtt_publisher.mqtt", mock_mqtt):
            publisher = MqttPublisher()
            result = publisher.send_device_command("fan", "off")
            assert result is False

    def test_send_multiple_commands(self):
        """Test sending multiple commands to different devices."""
        mock_mqtt = MagicMock()
        mock_mqtt.publish.return_value = True
        with patch("app.gateways.mqtt_publisher.mqtt", mock_mqtt):
            publisher = MqttPublisher()
            commands = [
                ("fan", "on"),
                ("light", "off"),
                ("ac", "cool")
            ]
            for device, cmd in commands:
                result = publisher.send_device_command(device, cmd)
                assert result is True

            assert mock_mqtt.publish.call_count == 3
            expected_calls = [
                call("home/control/fan", "on"),
                call("home/control/light", "off"),
                call("home/control/ac", "cool"),
            ]
            mock_mqtt.publish.assert_has_calls(expected_calls)

    def test_topic_format(self):
        """Test that the topic is formatted correctly."""
        mock_mqtt = MagicMock()
        with patch("app.gateways.mqtt_publisher.mqtt", mock_mqtt):
            publisher = MqttPublisher()
            publisher.send_device_command("bedroom_light", "on")
            call_args = mock_mqtt.publish.call_args
            topic, payload = call_args[0]
            assert topic == "home/control/bedroom_light"
            assert payload == "on"

    def test_special_characters_in_device_code(self):
        """Test device codes with special characters."""
        mock_mqtt = MagicMock()
        with patch("app.gateways.mqtt_publisher.mqtt", mock_mqtt):
            publisher = MqttPublisher()
            publisher.send_device_command("living-room_fan_1", "on")
            expected_topic = "home/control/living-room_fan_1"
            mock_mqtt.publish.assert_called_once_with(expected_topic, "on")

    def test_empty_payload(self):
        """Test sending empty payload."""
        mock_mqtt = MagicMock()
        mock_mqtt.publish.return_value = True
        with patch("app.gateways.mqtt_publisher.mqtt", mock_mqtt):
            publisher = MqttPublisher()
            result = publisher.send_device_command("device", "")
            assert result is True
            mock_mqtt.publish.assert_called_once_with("home/control/device", "")

    def test_large_payload(self):
        """Test sending large payload."""
        mock_mqtt = MagicMock()
        mock_mqtt.publish.return_value = True
        with patch("app.gateways.mqtt_publisher.mqtt", mock_mqtt):
            publisher = MqttPublisher()
            large_payload = "x" * 10000
            result = publisher.send_device_command("device", large_payload)
            assert result is True
            mock_mqtt.publish.assert_called_once_with("home/control/device", large_payload)
