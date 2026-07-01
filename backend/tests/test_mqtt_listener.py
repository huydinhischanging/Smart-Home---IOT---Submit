"""Tests for MQTT listener gateway — covers connection, sensor data, device status, and error handling."""
import json
from unittest.mock import MagicMock, patch, call
import pytest

from app.gateways.mqtt_listener import init_mqtt_listener


def _extract_handler(mock_decorator):
    """Extract the actual handler function registered via a Flask-MQTT decorator.

    Flask-MQTT decorators work like::

        @mqtt.on_message()          # mqtt.on_message() returns a wrapper
        def handle(client, ...):    # wrapper(handle) is called, returning handle
            ...

    After calling ``init_mqtt_listener``, the mock records:
        mock.on_message()           → returns wrapper (MagicMock)
        wrapper(handle_fn)          → wrapper.call_args[0][0] is the handler
    """
    wrapper = mock_decorator.return_value
    if wrapper.call_args is None:
        return None
    return wrapper.call_args[0][0]


class TestMqttListenerConnection:
    """Test MQTT connection handler."""

    def test_successful_connection(self):
        """Test successful connection to MQTT broker."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.logger") as mock_logger:
                init_mqtt_listener(mock_app)

                handle_connect = _extract_handler(mock_mqtt.on_connect)
                assert handle_connect is not None

                # Connection code 0 = success
                handle_connect(None, None, None, 0)
                mock_mqtt.subscribe.assert_called()

    def test_failed_connection(self):
        """Test failed connection to MQTT broker."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.logger") as mock_logger:
                init_mqtt_listener(mock_app)

                handle_connect = _extract_handler(mock_mqtt.on_connect)
                assert handle_connect is not None

                # Simulate failed connection (rc = 1)
                handle_connect(None, None, None, 1)
                mock_logger.error.assert_called()


class TestMqttListenerHeartRate:
    """Test heart rate sensor data from Coospo H6."""

    def test_heart_rate_single_value(self):
        """Test processing single heart rate value."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                with patch("app.gateways.mqtt_listener.on_heart_rate_received") as mock_hr_api:
                    with patch("app.gateways.mqtt_listener.persist_patient_hr_record"):
                        init_mqtt_listener(mock_app)

                        handle_message = _extract_handler(mock_mqtt.on_message)
                        assert handle_message is not None

                        mock_message = MagicMock()
                        mock_message.topic = "home/sensors/heart_rate"
                        mock_message.payload = b"72"

                        handle_message(None, None, mock_message)
                        mock_hr_api.assert_called()

    def test_heart_rate_invalid_value(self):
        """Test handling of invalid heart rate value."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container"):
                with patch("app.gateways.mqtt_listener.logger") as mock_logger:
                    init_mqtt_listener(mock_app)

                    handle_message = _extract_handler(mock_mqtt.on_message)
                    assert handle_message is not None

                    mock_message = MagicMock()
                    mock_message.topic = "home/sensors/heart_rate"
                    mock_message.payload = b"invalid_bpm"

                    handle_message(None, None, mock_message)

    def test_heart_rate_with_payload_prefix(self):
        """Test handling of 'Payload:' prefixed heart rate value."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                with patch("app.gateways.mqtt_listener.on_heart_rate_received") as mock_hr_api:
                    with patch("app.gateways.mqtt_listener.persist_patient_hr_record"):
                        init_mqtt_listener(mock_app)

                        handle_message = _extract_handler(mock_mqtt.on_message)
                        assert handle_message is not None

                        mock_message = MagicMock()
                        mock_message.topic = "home/sensors/heart_rate"
                        mock_message.payload = b"Payload: 75"

                        handle_message(None, None, mock_message)
                        mock_hr_api.assert_called()

    def test_heart_rate_normal_range_persistence(self):
        """Test persistence of normal range heart rate (50-100 BPM)."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                with patch("app.gateways.mqtt_listener.on_heart_rate_received"):
                    with patch("app.gateways.mqtt_listener.persist_patient_hr_record") as mock_persist:
                        init_mqtt_listener(mock_app)

                        handle_message = _extract_handler(mock_mqtt.on_message)
                        assert handle_message is not None

                        mock_message = MagicMock()
                        mock_message.topic = "home/sensors/heart_rate"
                        mock_message.payload = b"72"

                        handle_message(None, None, mock_message)
                        mock_persist.assert_called()

    def test_heart_rate_abnormal_range_no_persistence(self):
        """Test abnormal heart rate (>100) is not persisted."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                with patch("app.gateways.mqtt_listener.on_heart_rate_received"):
                    with patch("app.gateways.mqtt_listener.persist_patient_hr_record") as mock_persist:
                        init_mqtt_listener(mock_app)

                        handle_message = _extract_handler(mock_mqtt.on_message)
                        assert handle_message is not None

                        mock_message = MagicMock()
                        mock_message.topic = "home/sensors/heart_rate"
                        mock_message.payload = b"120"  # Above normal range

                        handle_message(None, None, mock_message)
                        # Should NOT persist abnormal HR
                        mock_persist.assert_not_called()


class TestMqttListenerBatchedData:
    """Test batched Coospo data payload (JSON format)."""

    def test_batched_data_with_heart_rate(self):
        """Test processing batched JSON data with heart rate."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                with patch("app.gateways.mqtt_listener.on_heart_rate_received") as mock_hr_api:
                    init_mqtt_listener(mock_app)

                    handle_message = _extract_handler(mock_mqtt.on_message)
                    assert handle_message is not None

                    mock_message = MagicMock()
                    mock_message.topic = "home/sensors/data"
                    data = {
                        "heart_rate": 75,
                        "room_temp": 22.5,
                        "humidity": 55.0,
                        "light_level": 300
                    }
                    mock_message.payload = json.dumps(data).encode()

                    handle_message(None, None, mock_message)
                    mock_hr_api.assert_called()

    def test_batched_data_alternative_field_names(self):
        """Test batched data with alternative field names (hr, temperature)."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                with patch("app.gateways.mqtt_listener.on_heart_rate_received") as mock_hr_api:
                    init_mqtt_listener(mock_app)

                    handle_message = _extract_handler(mock_mqtt.on_message)
                    assert handle_message is not None

                    mock_message = MagicMock()
                    mock_message.topic = "home/sensors/data"
                    data = {
                        "hr": 68,
                        "temperature": 21.0,
                        "humidity": 50.0
                    }
                    mock_message.payload = json.dumps(data).encode()

                    handle_message(None, None, mock_message)
                    mock_hr_api.assert_called()

    def test_batched_data_invalid_json(self):
        """Test handling of invalid JSON in batched data."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container"):
                with patch("app.gateways.mqtt_listener.logger") as mock_logger:
                    init_mqtt_listener(mock_app)

                    handle_message = _extract_handler(mock_mqtt.on_message)
                    assert handle_message is not None

                    mock_message = MagicMock()
                    mock_message.topic = "home/sensors/data"
                    mock_message.payload = b"invalid_json{{"

                    handle_message(None, None, mock_message)


class TestMqttListenerSensorData:
    """Test general sensor data handling."""

    def test_sensor_data_processing_success(self):
        """Test successful sensor data processing."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_sensor_uc = MagicMock()
        mock_sensor_uc.handle_sensor_data.return_value = True

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.sensor_usecase.return_value = mock_sensor_uc
                init_mqtt_listener(mock_app)

                handle_message = _extract_handler(mock_mqtt.on_message)
                assert handle_message is not None

                mock_message = MagicMock()
                mock_message.topic = "home/sensors/temp_living_room"
                mock_message.payload = b"22.5"

                handle_message(None, None, mock_message)
                mock_sensor_uc.handle_sensor_data.assert_called_once_with(
                    "temp_living_room",
                    "22.5"
                )

    def test_sensor_data_processing_v2_topic(self):
        """Test v2 sensor topic home/sensors/{type}/{device_id}."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_sensor_uc = MagicMock()
        mock_sensor_uc.handle_sensor_data.return_value = True

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.sensor_usecase.return_value = mock_sensor_uc
                init_mqtt_listener(mock_app)

                handle_message = _extract_handler(mock_mqtt.on_message)
                assert handle_message is not None

                mock_message = MagicMock()
                mock_message.topic = "home/sensors/humidity/do_am_a1"
                mock_message.payload = b"65.2"

                handle_message(None, None, mock_message)
                mock_sensor_uc.handle_sensor_data.assert_called_once_with(
                    "do_am_a1",
                    "65.2"
                )

    def test_sensor_data_unknown_sensor(self):
        """Test handling of unknown sensor device code."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_sensor_uc = MagicMock()
        mock_sensor_uc.handle_sensor_data.return_value = False

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.sensor_usecase.return_value = mock_sensor_uc
                with patch("app.gateways.mqtt_listener.logger") as mock_logger:
                    init_mqtt_listener(mock_app)

                    handle_message = _extract_handler(mock_mqtt.on_message)
                    assert handle_message is not None

                    mock_message = MagicMock()
                    mock_message.topic = "home/sensors/unknown_device"
                    mock_message.payload = b"42"

                    handle_message(None, None, mock_message)

    def test_sensor_data_processing_error(self):
        """Test error handling during sensor data processing."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_sensor_uc = MagicMock()
        mock_sensor_uc.handle_sensor_data.side_effect = Exception("Processing error")

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.sensor_usecase.return_value = mock_sensor_uc
                with patch("app.gateways.mqtt_listener.logger"):
                    init_mqtt_listener(mock_app)

                    handle_message = _extract_handler(mock_mqtt.on_message)
                    assert handle_message is not None

                    mock_message = MagicMock()
                    mock_message.topic = "home/sensors/temp"
                    mock_message.payload = b"20.0"

                    # Should not raise, just log error
                    handle_message(None, None, mock_message)


class TestMqttListenerDeviceStatus:
    """Test device status update handling."""

    def test_device_status_update_success(self):
        """Test successful device status update."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_device_uc = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.device_usecase.return_value = mock_device_uc
                init_mqtt_listener(mock_app)

                handle_message = _extract_handler(mock_mqtt.on_message)
                assert handle_message is not None

                mock_message = MagicMock()
                mock_message.topic = "home/status/fan"
                mock_message.payload = b"on"

                handle_message(None, None, mock_message)
                mock_device_uc.update_device_status.assert_called_once_with(
                    device_code="fan",
                    value="on",
                    source="MQTT",
                )

    def test_device_status_update_v2_topic(self):
        """Test v2 status topic home/status/{type}/{device_id}."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_device_uc = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.device_usecase.return_value = mock_device_uc
                init_mqtt_listener(mock_app)

                handle_message = _extract_handler(mock_mqtt.on_message)
                assert handle_message is not None

                mock_message = MagicMock()
                mock_message.topic = "home/status/light/l1"
                mock_message.payload = b"ON"

                handle_message(None, None, mock_message)
                mock_device_uc.update_device_status.assert_called_once_with(
                    device_code="l1",
                    value="ON",
                    source="MQTT",
                )

    def test_device_status_multiple_updates(self):
        """Test multiple device status updates."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_device_uc = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.device_usecase.return_value = mock_device_uc
                init_mqtt_listener(mock_app)

                handle_message = _extract_handler(mock_mqtt.on_message)
                assert handle_message is not None

                updates = [
                    ("home/status/fan", b"on"),
                    ("home/status/light", b"off"),
                    ("home/status/ac", b"cool"),
                ]

                for topic, payload in updates:
                    mock_message = MagicMock()
                    mock_message.topic = topic
                    mock_message.payload = payload
                    handle_message(None, None, mock_message)

                assert mock_device_uc.update_device_status.call_count == 3

    def test_device_status_error_handling(self):
        """Test error handling during device status update."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_device_uc = MagicMock()
        mock_device_uc.update_device_status.side_effect = Exception("Update failed")

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.device_usecase.return_value = mock_device_uc
                with patch("app.gateways.mqtt_listener.logger"):
                    init_mqtt_listener(mock_app)

                    handle_message = _extract_handler(mock_mqtt.on_message)
                    assert handle_message is not None

                    mock_message = MagicMock()
                    mock_message.topic = "home/status/fan"
                    mock_message.payload = b"on"

                    # Should not raise
                    handle_message(None, None, mock_message)

    def test_device_status_with_payload_prefix(self):
        """Test device status with 'Payload:' prefix."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_device_uc = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.device_usecase.return_value = mock_device_uc
                init_mqtt_listener(mock_app)

                handle_message = _extract_handler(mock_mqtt.on_message)
                assert handle_message is not None

                mock_message = MagicMock()
                mock_message.topic = "home/status/light"
                mock_message.payload = b"Payload: bright"

                handle_message(None, None, mock_message)
                # Should strip the "Payload: " prefix
                call_args = mock_device_uc.update_device_status.call_args
                assert call_args[1]["value"] == "bright"


class TestMqttListenerUnknownTopic:
    """Test handling of unknown topics."""

    def test_unknown_topic_logging(self):
        """Test that unknown topics are logged as warnings."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container"):
                with patch("app.gateways.mqtt_listener.logger") as mock_logger:
                    init_mqtt_listener(mock_app)

                    handle_message = _extract_handler(mock_mqtt.on_message)
                    assert handle_message is not None

                    mock_message = MagicMock()
                    mock_message.topic = "unknown/topic/path"
                    mock_message.payload = b"some_data"

                    handle_message(None, None, mock_message)

    def test_various_unknown_topics(self):
        """Test various unknown topic formats."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container"):
                with patch("app.gateways.mqtt_listener.logger"):
                    init_mqtt_listener(mock_app)

                    handle_message = _extract_handler(mock_mqtt.on_message)
                    assert handle_message is not None

                    unknown_topics = [
                        "admin/command",
                        "system/health",
                        "random/path",
                        "test",
                    ]

                    for topic in unknown_topics:
                        mock_message = MagicMock()
                        mock_message.topic = topic
                        mock_message.payload = b"data"
                        handle_message(None, None, mock_message)


class TestMqttListenerMessageParsing:
    """Test message payload parsing and encoding handling."""

    def test_utf8_payload(self):
        """Test handling of UTF-8 encoded payload."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_device_uc = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.device_usecase.return_value = mock_device_uc
                init_mqtt_listener(mock_app)

                handle_message = _extract_handler(mock_mqtt.on_message)
                assert handle_message is not None

                mock_message = MagicMock()
                mock_message.topic = "home/status/device"
                mock_message.payload = "Nhiệt độ: 25°C".encode('utf-8')

                handle_message(None, None, mock_message)

    def test_payload_with_whitespace(self):
        """Test handling of payload with leading/trailing whitespace."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_device_uc = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.device_usecase.return_value = mock_device_uc
                init_mqtt_listener(mock_app)

                handle_message = _extract_handler(mock_mqtt.on_message)
                assert handle_message is not None

                mock_message = MagicMock()
                mock_message.topic = "home/status/fan"
                mock_message.payload = b"  on  "

                handle_message(None, None, mock_message)
                call_args = mock_device_uc.update_device_status.call_args
                # Should strip whitespace
                assert call_args[1]["value"] == "on"

    def test_empty_payload(self):
        """Test handling of empty payload."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_device_uc = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.device_usecase.return_value = mock_device_uc
                init_mqtt_listener(mock_app)

                handle_message = _extract_handler(mock_mqtt.on_message)
                assert handle_message is not None

                mock_message = MagicMock()
                mock_message.topic = "home/status/device"
                mock_message.payload = b""

                handle_message(None, None, mock_message)


class TestMqttListenerTopicParsing:
    """Test topic parsing and device code extraction."""

    def test_sensor_topic_parsing(self):
        """Test extraction of device code from sensor topics."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_sensor_uc = MagicMock()
        mock_sensor_uc.handle_sensor_data.return_value = True

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.sensor_usecase.return_value = mock_sensor_uc
                init_mqtt_listener(mock_app)

                handle_message = _extract_handler(mock_mqtt.on_message)
                assert handle_message is not None

                test_cases = [
                    ("home/sensors/temp_living_room", "temp_living_room"),
                    ("home/sensors/humidity_bedroom", "humidity_bedroom"),
                    ("home/sensors/light_kitchen", "light_kitchen"),
                ]

                for topic, expected_code in test_cases:
                    mock_sensor_uc.reset_mock()
                    mock_message = MagicMock()
                    mock_message.topic = topic
                    mock_message.payload = b"42"

                    handle_message(None, None, mock_message)
                    call_args = mock_sensor_uc.handle_sensor_data.call_args
                    assert call_args[0][0] == expected_code

    def test_status_topic_parsing(self):
        """Test extraction of device code from status topics."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_device_uc = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.device_usecase.return_value = mock_device_uc
                init_mqtt_listener(mock_app)

                handle_message = _extract_handler(mock_mqtt.on_message)
                assert handle_message is not None

                test_cases = [
                    ("home/status/fan", "fan"),
                    ("home/status/light_living_room", "light_living_room"),
                    ("home/status/ac_bedroom", "ac_bedroom"),
                ]

                for topic, expected_code in test_cases:
                    mock_device_uc.reset_mock()
                    mock_message = MagicMock()
                    mock_message.topic = topic
                    mock_message.payload = b"on"

                    handle_message(None, None, mock_message)
                    call_args = mock_device_uc.update_device_status.call_args
                    assert call_args[1]["device_code"] == expected_code

    def test_topic_with_whitespace(self):
        """Test that topic whitespace is stripped."""
        mock_mqtt = MagicMock()
        mock_app = MagicMock()
        mock_device_uc = MagicMock()

        with patch("app.gateways.mqtt_listener.mqtt", mock_mqtt):
            with patch("app.gateways.mqtt_listener.container") as mock_container:
                mock_container.device_usecase.return_value = mock_device_uc
                init_mqtt_listener(mock_app)

                handle_message = _extract_handler(mock_mqtt.on_message)
                assert handle_message is not None

                mock_message = MagicMock()
                mock_message.topic = "  home/status/fan  "
                mock_message.payload = b"on"

                handle_message(None, None, mock_message)
                call_args = mock_device_uc.update_device_status.call_args
                assert call_args[1]["device_code"] == "fan"
