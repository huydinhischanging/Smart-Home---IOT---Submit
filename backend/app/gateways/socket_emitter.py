# app/gateways/socket_emitter.py
import logging

logger = logging.getLogger(__name__)


class SocketEmitter:
    """
    OUTPUT Gateway
    Cầu nối giữa Application Layer và Flask-SocketIO
    """

    def __init__(self):
        # ✅ Import lồng để tránh circular import
        from app.extensions.socketio import socketio
        self.socketio = socketio

    # ======================================================
    # GENERIC EMIT (QUAN TRỌNG NHẤT)
    # ======================================================
    def emit(self, event: str, data: dict, room=None):
        """
        Hàm trung tâm để gửi event realtime lên frontend.
        RealtimeNotifier sẽ gọi hàm này.
        """
        try:
            if room is not None:
                self.socketio.emit(event, data, room=room)
            else:
                self.socketio.emit(event, data)
            # Có thể bật log nếu muốn debug
            # print(f"📡 [SOCKET EMIT] {event} -> {data}")
        except Exception as e:
            logger.error("[SOCKET ERROR] Could not emit '%s': %s", event, e)

    # ======================================================
    # OPTIONAL: BACKWARD COMPATIBILITY METHODS
    # (Nếu nơi khác trong hệ thống còn dùng)
    # ======================================================
    def emit_device_status(self, device_name: str, payload: str):
        self.emit("device_status", {
            "device_name": device_name,
            "payload": payload
        })

    def emit_device_list_changed(self):
        self.emit("device_list_changed", {})