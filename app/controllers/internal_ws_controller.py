import json
from flask import Blueprint, request, jsonify, current_app
from app.services.websocket_service import socketio
from app.models.booking import Booking
from app.models.user import User
from app.models.availableGame import AvailableGame
from app.models.vendor import Vendor
from app.extension.extensions import db
from app.services.websocket_service import _emit_to_kiosk
from datetime import datetime, timezone as dt_timezone
import pytz

bp_internal_ws = Blueprint('internal_ws', __name__, url_prefix='/internal/ws')

# Define IST
IST = pytz.timezone("Asia/Kolkata")

def ensure_ist(dt_obj):
    """Ensure a datetime is timezone-aware in IST (idempotent)."""
    if dt_obj is None:
        return None
    if dt_obj.tzinfo is None:
        return IST.localize(dt_obj)
    return dt_obj.astimezone(IST)


@bp_internal_ws.post('/unlock')
def internal_send_unlock():
    # Even an internal caller cannot choose its own paid-session deadline.
    from app.services.kiosk_security import runtime_identity, check_scope, positive_id, KioskError
    from app.services.kiosk_runtime import booking_window
    identity = runtime_identity()
    data = request.get_json(silent=True) or {}
    console_id = positive_id(data.get("console_id"))
    check_scope(identity, identity["vendor_id"], console_id)
    window = booking_window(identity["vendor_id"], positive_id(data.get("booking_id")), console_id)
    if window["status"] != "active":
        raise KioskError("session_ended", 409)
    _emit_to_kiosk(console_id, "unlock_request", dict(window, type="unlock_request"))
    return jsonify({"status": "success"}), 200


@bp_internal_ws.post('/store-updated')
def internal_store_updated():
    """
    Internal endpoint to notify dashboard clients that store inventory/products changed.
    Payload:
      { "vendor_id": 123 }  # optional; if omitted, broadcast to all
    """
    try:
        data = request.get_json(silent=True) or {}
        vendor_id = data.get("vendor_id")
        payload = {"vendor_id": vendor_id} if vendor_id else {}

        if vendor_id:
            socketio.emit("store_updated", payload, room=f"vendor_{int(vendor_id)}")
        else:
            socketio.emit("store_updated", payload, broadcast=True)

        return jsonify({"ok": True}), 200
    except Exception as e:
        current_app.logger.exception("Internal WS store_updated failed")
        return jsonify({"error": str(e)}), 500
