import json
from flask import Blueprint, request, jsonify, current_app
from app.services.websocket_service import socketio
from app.models.booking import Booking
from app.models.user import User
from app.models.availableGame import AvailableGame
from app.models.vendor import Vendor
from app.extension.extensions import db
from app.services.websocket_service import _emit_to_kiosk

bp_internal_ws = Blueprint('internal_ws', __name__, url_prefix='/internal/ws')

@bp_internal_ws.post('/unlock')
def internal_send_unlock():
    """
    Internal endpoint to broadcast unlock events to a specific vendor room over WebSocket.
    """
    try:
        data = request.get_json(silent=True) or {}
        console_id = data.get("console_id")
        booking_id = data.get("booking_id")
        start_time = data.get("start_time")
        end_time = data.get("end_time")

        # Validate input
        if not all([console_id, booking_id, start_time, end_time]):
            return jsonify({"error": "Missing required fields"}), 400

        # Fetch booking details
        booking_record = (
            db.session.query(Booking)
            .filter(Booking.id == booking_id)
            .join(AvailableGame, Booking.game_id == AvailableGame.id)
            .join(User, Booking.user_id == User.id)
            .join(Vendor, AvailableGame.vendor_id == Vendor.id)
            .add_entity(AvailableGame)
            .add_entity(User)
            .add_entity(Vendor)
            .first()
        )

        if not booking_record:
            return jsonify({"error": "Booking not found"}), 404

        booking, game, user, vendor = booking_record  # unpack

        # Construct payload
        payload = {
            "type": "unlock_request",
            "console_id": console_id,
            "data": {
                "booking_id": booking.id,
                "start_time": start_time,
                "end_time": end_time,
                "user_id": user.id,
                "user_name": user.name,
                "vendor_id": vendor.id,
                "vendor_name": vendor.cafe_name,
                "game_id": booking.game_id,
                "game_name": game.game_name
            },
        }

        _emit_to_kiosk(kiosk_id=console_id, event="unlock_request", data=payload)

        current_app.logger.info("Unlock request sent to kiosk room ")
        return jsonify({"ok": True}), 200

    except Exception as e:
        current_app.logger.exception("Internal WS Unlock failed")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
