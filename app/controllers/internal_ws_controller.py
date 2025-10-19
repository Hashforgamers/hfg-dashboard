import json
import logging
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from app.services.websocket_service import socketio # your initialized SocketIO

bp_internal_ws = Blueprint('internal_ws', __name__, url_prefix='/internal/ws')

# Configure logger (only once)
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] - %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


@bp_internal_ws.post('/unlock')
def internal_send_unlock():
    try:
        # Parse JSON safely
        data = request.get_json(force=True)
        console_id = data.get('console_id')
        booking_id = data.get('booking_id')
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        # Validate inputs
        if not all([console_id, booking_id, start_time, end_time]):
            logger.warning(f"⚠️ Missing fields in request: {data}")
            return jsonify({"error": "Missing required fields"}), 400

        payload = {
            "type": "unlock_request",
            "console_id": console_id,
            "data": {
                "booking_id": booking_id,
                "start_time": start_time,
                "end_time": end_time,
            },
        }

        # Log received unlock request
        logger.info(f"🔓 Unlock request received: {json.dumps(payload, indent=2)}")

        # Emit over socket
        socketio.emit('message', payload, room=f"console:{console_id}")

        logger.debug(f"📤 Emitted unlock event to room console:{console_id}")

        return jsonify({"ok": True})

    except Exception as e:
        logger.exception(f"❌ Internal WS Unlock failed: {e}")
        return jsonify({"error": str(e)}), 500
