# app/services/booking_bridge.py
import os
import logging
import threading
from typing import Optional, Set, Dict, Any

import socketio

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BOOKING_SOCKET_URL = os.getenv("BOOKING_SOCKET_URL", "wss://hfg-booking-hmnx.onrender.com")
BOOKING_NAMESPACE = os.getenv("BOOKING_BRIDGE_NAMESPACE")  # optional, e.g. "/booking"

_sio = socketio.Client(
    reconnection=True,
    reconnection_attempts=0,      # infinite
    reconnection_delay=1.0,
    reconnection_delay_max=10.0,
    logger=False,
    engineio_logger=False,
)

# Track which vendor rooms we've asked to join upstream to avoid duplicates
_joined_vendor_ids: Set[int] = set()
_started = False
_lock = threading.Lock()


def _join_upstream_vendor(vendor_id: int):
    """Ask booking service to add this client to vendor_{vendor_id} room (idempotent)."""
    payload = {"vendor_id": int(vendor_id)}
    if BOOKING_NAMESPACE:
        _sio.emit("connect_vendor", payload, namespace=BOOKING_NAMESPACE)
    else:
        _sio.emit("connect_vendor", payload)
    logger.info("Upstream join requested: vendor_%s", vendor_id)


@_sio.event
def connect():
    logger.info("Connected to booking upstream: %s", BOOKING_SOCKET_URL)
    # Re-join all vendors after reconnect
    with _lock:
        vendors = list(_joined_vendor_ids)
    for vid in vendors:
        _join_upstream_vendor(vid)


@_sio.event
def disconnect():
    logger.warning("Disconnected from booking upstream")


def _emit_downstream(vendor_id: Optional[int], data: Dict[str, Any]):
    """Emit to local dashboard clients subscribed to vendor_{vendor_id} room only."""
    try:
        from app.services.websocket_service import socketio as dashboard_socketio
        room = f"vendor_{vendor_id}" if vendor_id is not None else None
        if room:
            dashboard_socketio.emit("booking_update", data, room=room)
        else:
            # Fallback: if no vendor_id present, emit globally or to a default topic
            dashboard_socketio.emit("booking_update", data, broadcast=True)
    except Exception:
        logger.exception("Downstream emit failed")


def _handle_booking_event(data):
    try:
        vendor_id = data.get("vendorId") or data.get("vendor_id")
        booking_id = data.get("bookingId") or data.get("booking_id")
        logger.info("Upstream booking: vendor=%s bookingId=%s", vendor_id, booking_id)
        _emit_downstream(vendor_id, data)
    except Exception:
        logger.exception("Error handling upstream booking event")


def _register_booking_listener():
    event_name = "booking"

    if BOOKING_NAMESPACE:
        @_sio.on(event_name, namespace=BOOKING_NAMESPACE)
        def _on_booking_ns(data):
            _handle_booking_event(data)
    else:
        @_sio.on(event_name)
        def _on_booking(data):
            _handle_booking_event(data)


def start_bridge():
    """Start the upstream bridge once (idempotent)."""
    global _started
    with _lock:
        if _started:
            return
        _started = True

    _register_booking_listener()

    def _run():
        try:
            _sio.connect(BOOKING_SOCKET_URL, transports=["websocket"])
            _sio.wait()
        except Exception:
            logger.exception("Booking WS bridge connection error")

    t = threading.Thread(target=_run, name="booking-bridge", daemon=True)
    t.start()


def ensure_upstream_vendor_join(vendor_id: int):
    """Public: called when any dashboard client wants vendor_{vendor_id}.
    Caches vendor_id and triggers upstream join if not already joined.
    """
    with _lock:
        is_new = int(vendor_id) not in _joined_vendor_ids
        if is_new:
            _joined_vendor_ids.add(int(vendor_id))
    if is_new and _sio.connected:
        _join_upstream_vendor(int(vendor_id))


def bridge_status() -> dict:
    with _lock:
        joined = sorted(list(_joined_vendor_ids))
    return {
        "connected": bool(getattr(_sio, "connected", False)),
        "joined_vendor_ids": joined,
        "url": BOOKING_SOCKET_URL,
        "namespace": BOOKING_NAMESPACE or "",
    }
