# dashboard_service/controllers/internal_ws_controller.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.socket import socketio  # your initialized SocketIO
from datetime import datetime

bp_internal_ws = Blueprint('internal_ws', __name__, url_prefix='/internal/ws')

@bp_internal_ws.post('/unlock')
def internal_send_unlock():
    # Add an HMAC or internal bearer token check here
    data = request.get_json()
    console_id = data['console_id']
    booking_id = data['booking_id']
    start_time = data['start_time']   # ISO8601
    end_time = data['end_time']       # ISO8601
    payload = {
        "type":"unlock_request",
        "console_id": console_id,
        "data": {
            "booking_id": booking_id,
            "start_time": start_time,
            "end_time": end_time
        }
    }
    socketio.emit('message', payload, room=f"console:{console_id}")
    return jsonify({"ok": True})
