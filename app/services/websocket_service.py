# app/services/websocket_service.py
import os
import json
import logging
import threading
from typing import Dict, Any, Optional, Set

from flask import current_app
from flask_socketio import SocketIO, join_room
import socketio  # python-socketio (client)

# -----------------------------------------------------------------------------
# Dashboard-side Socket.IO server (used by your dashboard clients)
# -----------------------------------------------------------------------------
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode=None,  # eventlet/gevent/threading – auto-select based on installed libs
)

# -----------------------------------------------------------------------------
# Upstream booking service Socket.IO client (single persistent connection)
# -----------------------------------------------------------------------------
BOOKING_SOCKET_URL = os.getenv("BOOKING_SOCKET_URL", "wss://hfg-booking-hmnx.onrender.com")
BOOKING_NAMESPACE = os.getenv("BOOKING_BRIDGE_NAMESPACE")  # e.g. "/booking" or None
BOOKING_AUTH_TOKEN = os.getenv("BOOKING_AUTH_TOKEN")       # optional Authorization header

_upstream_sio = socketio.Client(
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
# Internal helpers
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

def _emit_downstream_to_vendor(vendor_id: Optional[int], event: str, data: Dict[str, Any]):
    """
    Emit to local dashboard clients in room vendor_{vendor_id}.
    Falls back to broadcast if vendor_id missing.
    """
    try:
        if vendor_id is not None:
            room = f"vendor_{int(vendor_id)}"
            socketio.emit(event, data, room=room)
        else:
            socketio.emit(event, data, broadcast=True)
    except Exception:
        _log_err("Downstream emit failed for event=%s vendor=%s", event, vendor_id)

def _join_upstream_vendor(vendor_id: int):
    payload = {"vendor_id": int(vendor_id)}
    try:
        if BOOKING_NAMESPACE:
            _upstream_sio.emit("connect_vendor", payload, namespace=BOOKING_NAMESPACE)
        else:
            _upstream_sio.emit("connect_vendor", payload)
        _log_info("Upstream join requested: vendor_%s", vendor_id)
    except Exception:
        _log_err("Failed to request upstream join for vendor_%s", vendor_id)

def _handle_upstream_booking(data: Dict[str, Any]):
    try:
        vendor_id = data.get("vendorId") or data.get("vendor_id")
        booking_id = data.get("bookingId") or data.get("booking_id")
        _log_info("[Upstream booking] vendor=%s bookingId=%s", vendor_id, booking_id)
        _emit_downstream_to_vendor(vendor_id, "booking_update", data)
    except Exception:
        _log_err("Error handling upstream booking payload")

def _register_upstream_handlers():
    # connection lifecycle
    @_upstream_sio.event
    def connect():
        _log_info("Connected to booking upstream: %s", BOOKING_SOCKET_URL)
        # Re-join all known vendor rooms after reconnect
        with _lock:
            vendors = list(_joined_vendor_ids)
        for vid in vendors:
            _join_upstream_vendor(vid)

    @_upstream_sio.event
    def disconnect():
        _log_warn("Disconnected from booking upstream")

    # booking event listener
    if BOOKING_NAMESPACE:
        @_upstream_sio.on("booking", namespace=BOOKING_NAMESPACE)
        def _on_booking_ns(data):
            _handle_upstream_booking(data)
    else:
        @_upstream_sio.on("booking")
        def _on_booking(data):
            _handle_upstream_booking(data)

# -----------------------------------------------------------------------------
# Public: start background upstream bridge
# -----------------------------------------------------------------------------
def start_upstream_bridge(app):
    """
    Start the upstream Socket.IO client in a background thread.
    Idempotent; safe to call once during app startup.
    """
    global _started_upstream
    with _lock:
        if _started_upstream:
            return
        _started_upstream = True

    _register_upstream_handlers()

    def _runner():
        try:
            connect_kwargs = dict(transports=["websocket"])
            headers = None
            if BOOKING_AUTH_TOKEN:
                headers = {"Authorization": f"Bearer {BOOKING_AUTH_TOKEN}"}
                connect_kwargs["headers"] = headers
            _upstream_sio.connect(BOOKING_SOCKET_URL, **connect_kwargs)
            _upstream_sio.wait()
        except Exception as e:
            _log_err("Upstream bridge connection error: %s", e)

    t = threading.Thread(target=_runner, name="booking-upstream-bridge", daemon=True)
    t.start()

# -----------------------------------------------------------------------------
# Dashboard (local) socket event registration
# -----------------------------------------------------------------------------
def register_dashboard_events():
    """
    Register events that your dashboard clients will use.
    - dashboard_join_vendor: client declares which vendor_id it cares about.
      Server joins client to local room vendor_{vendor_id} and ensures the
      upstream connection is subscribed to that vendor room.
    - demo events preserved from your previous code.
    """
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

            # Ensure upstream is joined once per vendor (idempotent)
            with _lock:
                is_new = int(vendor_id) not in _joined_vendor_ids
                if is_new:
                    _joined_vendor_ids.add(int(vendor_id))
            if is_new and _upstream_sio.connected:
                _join_upstream_vendor(int(vendor_id))
        except Exception as e:
            _log_err("dashboard_join_vendor error: %s", e)

    # ---------------------------
    # Demo/test handlers you had
    # ---------------------------
    @socketio.on('slot_booked_demo')
    def handle_slot_booked(data):
        try:
            # Accept dict or JSON string
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
