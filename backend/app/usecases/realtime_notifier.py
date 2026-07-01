# app/usecases/realtime_notifier.py

class RealtimeNotifier:
    """
    Application layer
    Gửi event realtime ra frontend thông qua SocketEmitter
    """

    def __init__(self, socket_emitter):
        # ⚠️ TÊN NÀY PHẢI TRÙNG với wiring.py inject vào
        self.socket_emitter = socket_emitter

    @staticmethod
    def _room(user_id):
        return f"user_{user_id}" if user_id is not None else None

    # =====================================================
    # DEVICE STATUS
    # =====================================================
    def notify_device_status(self, payload: dict, user_id=None):
        self.socket_emitter.emit("device_status", payload, room=self._room(user_id))

    # =====================================================
    # DEVICE LIST CHANGED
    # =====================================================
    def notify_device_list_changed(self, user_id=None):
        self.socket_emitter.emit("device_list_changed", {}, room=self._room(user_id))

    # =====================================================
    # ALERT
    # =====================================================
    def notify_alert(self, payload: dict, user_id=None):
        self.socket_emitter.emit("alert", payload, room=self._room(user_id))

    # =====================================================
    # AI MOOD
    # =====================================================
    def notify_ai_mood(self, payload: dict, user_id=None):
        self.socket_emitter.emit("ai_mood", payload, room=self._room(user_id))

    # =====================================================
    # AI ADVICE
    # =====================================================
    def notify_ai_advice(self, payload: dict, user_id=None):
        self.socket_emitter.emit("ai_advice", payload, room=self._room(user_id))

    # =====================================================
    # AI EXPLAIN
    # =====================================================
    def notify_ai_explain(self, payload: dict, user_id=None):
        self.socket_emitter.emit("ai_explain", payload, room=self._room(user_id))

    # =====================================================
    # SOS ALERT (chat-triggered)
    # =====================================================
    def notify_sos_alert(self, payload: dict, user_id=None):
        self.socket_emitter.emit("sos_alert", payload, room=self._room(user_id))