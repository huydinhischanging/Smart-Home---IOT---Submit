from flask_socketio import SocketIO
import logging

_logger = logging.getLogger(__name__)

# Use threading mode — stable, no deprecated dependencies.
# eventlet is deprecated upstream; threading works reliably for this project.
socketio = SocketIO(
    async_mode="threading",
    logger=True,
    engineio_logger=True
)
