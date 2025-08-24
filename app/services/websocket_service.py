# app/services/websocket_service.py
import os
import json
import logging
import threading
from typing import Dict, Any, Optional, Set

from flask import current_app
from flask_socketio import SocketIO, join_room
import socketio as pwsio   # python-socketio client (aliased)
from services.payload_formatters import format_upcoming_booking_from_upstream


# -----------------------------------------------------------------------------
# Dashboard Socket.IO server (clients connect here)
# -----------------------------------------------------------------------------
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode=None,
)

# -----------------------------------------------------------------------------
# Upstream booking service client (single persistent connection)
# -----------------------------------------------------------------------------
BOOKING_SOCKET_URL = os.getenv("BOOKING_SOCKET_URL", "wss://hfg-booking-hmnx.onrender.com")
BOOKING_NAMESPACE = os.getenv("BOOKING_BRIDGE_NAMESPACE")  # keep unset for default "/"
BOOKING_AUTH_TOKEN = os.getenv("BOOKING_AUTH_TOKEN")       # optional bearer token

_upstream_sio = pwsio.Client(
    reconnection=True,
    reconnection_attempts=0,      # infinite
    reconnection_delay=1.0,
    reconnection_delay_max=10.0,
    logger=False,
    engineio_logger=False,
)

_started_upstream = False
_joined_vendor_ids: Set[int] = set()
_lock = threading.Lock()

# -----------------------------------------------------------------------------
# Logging helpers
# -----------------------------------------------------------------------------
def _log_info(msg: str, *args):
    try:
        current_app.logger.info(msg, *args)
    except Exception:
        logging.getLogger(__name__).info(msg, *args)

def _log_warn(msg: str, *args):
    try:
        current_app.logger.warning(msg, *args)
    except Exception:
        logging.getLogger(__name__).warning(msg, *args)

def _log_err(msg: str, *args):
    try:
        current_app.logger.error(msg, *args)
    except Exception:
        logging.getLogger(__name__).error(msg, *args)

# -----------------------------------------------------------------------------
# Downstream emit (to dashboard clients)
# -----------------------------------------------------------------------------
def _emit_downstream_to_vendor(vendor_id: Optional[int], event: str, data: Dict[str, Any]):
    try:
        if vendor_id is not None:
            room = f"vendor_{int(vendor_id)}"
            _log_info("Emitting %s to %s", event, room)
            socketio.emit(event, data, room=room)
        else:
            _log_info("Emitting %s to broadcast", event)
            socketio.emit(event, data, broadcast=True)
    except Exception:
        _log_err("Downstream emit failed event=%s vendor=%s", event, vendor_id)

# -----------------------------------------------------------------------------
# Upstream helpers
# -----------------------------------------------------------------------------
def _join_upstream_vendor(vendor_id: int):
    payload = {"vendor_id": int(vendor_id)}
    try:
        if BOOKING_NAMESPACE:
            _upstream_sio.emit("connect_vendor", payload, namespace=BOOKING_NAMESPACE)
        else:
            _upstream_sio.emit("connect_vendor", payload)
        _log_info("Upstream join requested: vendor_%s", vendor_id)
    except Exception:
        _log_err("Failed upstream join for vendor_%s", vendor_id)

def _join_upstream_admin():
    """Join the admin tap that receives ALL bookings."""
    try:
        if BOOKING_NAMESPACE:
            _upstream_sio.emit("connect_admin", {}, namespace=BOOKING_NAMESPACE)
        else:
            _upstream_sio.emit("connect_admin", {})
        _log_info("Requested admin tap: dashboard_admin")
    except Exception:
        _log_err("Failed to request admin tap (connect_admin)")

def _handle_upstream_booking(data: Dict[str, Any]):
    try:
        vendor_id = data.get("vendorId") or data.get("vendor_id")
        booking_id = data.get("bookingId") or data.get("booking_id")
        _log_info("[Upstream booking] vendor=%s bookingId=%s", vendor_id, booking_id)

        # Always relay raw event for general consumers
        _emit_downstream_to_vendor(vendor_id, "booking", data)

        # Only emit upcoming for confirmed bookings
        upcoming_payload = format_upcoming_booking_from_upstream(data)
        if upcoming_payload:
            _emit_downstream_to_vendor(vendor_id, "upcoming_booking", upcoming_payload)
            _log_info("Emitted dashboard_upcoming_booking (confirmed) vendor=%s bookingId=%s", vendor_id, booking_id)

    except Exception:
        _log_err("Error handling upstream booking payload")



def _register_upstream_handlers():
    @_upstream_sio.event
    def connect():
        _log_info("Connected to booking upstream: %s (namespace=%s)", BOOKING_SOCKET_URL, BOOKING_NAMESPACE or "/")
        # Always join the admin tap to receive ALL events
        _join_upstream_admin()
        # Optionally re-join vendor-specific rooms (if you still use that path)
        with _lock:
            vendors = list(_joined_vendor_ids)
        for vid in vendors:
            _join_upstream_vendor(vid)

    @_upstream_sio.event
    def disconnect():
        _log_warn("Disconnected from booking upstream")

    # Per-vendor event listener (if upstream puts this client in vendor rooms)
    if BOOKING_NAMESPACE:
        @_upstream_sio.on("booking", namespace=BOOKING_NAMESPACE)
        def _on_booking_ns(data):
            _handle_upstream_booking(data)
    else:
        @_upstream_sio.on("booking")
        def _on_booking(data):
            _handle_upstream_booking(data)

    # Admin tap listener: receives ALL booking events
    if BOOKING_NAMESPACE:
        @_upstream_sio.on("booking_admin", namespace=BOOKING_NAMESPACE)
        def _on_booking_admin_ns(data):
            _handle_upstream_booking(data)
    else:
        @_upstream_sio.on("booking_admin")
        def _on_booking_admin(data):
            _handle_upstream_booking(data)

# -----------------------------------------------------------------------------
# Public: start upstream bridge
# -----------------------------------------------------------------------------
def start_upstream_bridge(app):
    global _started_upstream
    with _lock:
        if _started_upstream:
            return
        _started_upstream = True

    _register_upstream_handlers()

    def _runner():
        try:
            kwargs = {}
            if BOOKING_AUTH_TOKEN:
                kwargs["headers"] = {"Authorization": f"Bearer {BOOKING_AUTH_TOKEN}"}
            # Let engine negotiate transports; avoids proxies that block direct WS
            _upstream_sio.connect(BOOKING_SOCKET_URL, **kwargs)
            _upstream_sio.wait()
        except Exception as e:
            _log_err("Upstream bridge connection error: %s", e)

    t = threading.Thread(target=_runner, name="booking-upstream-bridge", daemon=True)
    t.start()

# -----------------------------------------------------------------------------
# Dashboard (local) socket events
# -----------------------------------------------------------------------------
def register_dashboard_events():
    @socketio.on("connect")
    def _on_connect():
        _log_info("Dashboard client connected")

    @socketio.on("disconnect")
    def _on_disconnect():
        _log_info("Dashboard client disconnected")

    @socketio.on("dashboard_join_vendor")
    def _on_dashboard_join_vendor(data: Dict[str, Any]):
        try:
            vendor_id = data.get("vendor_id") or data.get("vendorId")
            if not vendor_id:
                _log_warn("dashboard_join_vendor missing vendor_id")
                return
            room = f"vendor_{int(vendor_id)}"
            join_room(room)
            _log_info("Dashboard client joined local room %s", room)

            # Optional: still ask upstream to join the vendor room (not required if using admin tap)
            with _lock:
                is_new = int(vendor_id) not in _joined_vendor_ids
                if is_new:
                    _joined_vendor_ids.add(int(vendor_id))
            if is_new and _upstream_sio.connected:
                _join_upstream_vendor(int(vendor_id))
        except Exception as e:
            _log_err("dashboard_join_vendor error: %s", e)

    # Demo/test events remain (optional)
    @socketio.on('slot_booked_demo')
    def handle_slot_booked(data):
        try:
            if isinstance(data, str):
                data = json.loads(data)
            current_app.logger.info("slot_booked_demo: %s", data)
            socketio.emit('slot_booked', {'slot_id': data.get('slot_id'), 'status': 'booked'})
        except Exception as e:
            _log_err("slot_booked_demo error: %s", e)

    @socketio.on('booking_updated_demo')
    def handle_booking_updated(data):
        try:
            current_app.logger.info("booking_updated_demo: %s", data)
            socketio.emit('booking_updated', data)
        except Exception as e:
            _log_err("booking_updated_demo error: %s", e)
