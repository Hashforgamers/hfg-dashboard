import os
import json
import logging
import threading
import time
from typing import Dict, Any, Optional, Set

from flask import current_app
from flask_socketio import SocketIO, join_room, emit
import socketio as pwsio   # python-socketio client (aliased)
from app.services.payload_formatters import format_upcoming_booking_from_upstream

# -----------------------------------------------------------------------------
# Dashboard Socket.IO server (clients connect here)
# -----------------------------------------------------------------------------
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode=None,  # gevent/eventlet auto if patched; falls back to threading
)

# -----------------------------------------------------------------------------
# Upstream booking service client (single persistent connection)
# -----------------------------------------------------------------------------
BOOKING_SOCKET_URL = os.getenv("BOOKING_SOCKET_URL", "wss://hfg-booking-hmnx.onrender.com")
BOOKING_NAMESPACE = os.getenv("BOOKING_BRIDGE_NAMESPACE")  # unset or "/" => default namespace
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

# Heartbeat tracking
_last_admin_heartbeat = 0.0
_last_pong = 0.0
_UPSTREAM_PING_TIMEOUT = 10.0  # seconds to consider pong overdue
_HEALTH_INTERVAL = 15          # seconds between health checks
_REJOIN_QUIET_SECS = 60        # if no traffic for this long, re-join admin

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _ns() -> Optional[str]:
    """Normalize namespace: return None for default, otherwise '/name'."""
    ns = (BOOKING_NAMESPACE or "").strip()
    if not ns or ns == "/":
        return None
    return ns if ns.startswith("/") else f"/{ns}"

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

def _mark_pong():
    global _last_pong, _last_admin_heartbeat
    now = time.time()
    _last_pong = now
    _last_admin_heartbeat = now  # treat any upstream response as heartbeat

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
        ns = _ns()
        if ns:
            _upstream_sio.emit("connect_vendor", payload, namespace=ns)
        else:
            _upstream_sio.emit("connect_vendor", payload)
        _log_info("Upstream join requested: vendor_%s", vendor_id)
    except Exception:
        _log_err("Failed upstream join for vendor_%s", vendor_id)

def _join_upstream_admin():
    """Join the admin tap that receives ALL bookings."""
    try:
        ns = _ns()
        if ns:
            _upstream_sio.emit("connect_admin", {}, namespace=ns)
        else:
            _upstream_sio.emit("connect_admin", {})
        _log_info("Requested admin tap: dashboard_admin")
    except Exception:
        _log_err("Failed to request admin tap (connect_admin)")

def _handle_upstream_booking(data: Dict[str, Any]):
    try:
        _mark_pong()
        vendor_id = data.get("vendorId") or data.get("vendor_id")
        booking_id = data.get("bookingId") or data.get("booking_id")
        _log_info("[Upstream booking] vendor=%s bookingId=%s", vendor_id, booking_id)

        # Always relay raw event for general consumers
        _emit_downstream_to_vendor(vendor_id, "booking", data)

        # Emit upcoming for confirmed bookings
        upcoming_payload = format_upcoming_booking_from_upstream(data)
        if upcoming_payload:
            _emit_downstream_to_vendor(vendor_id, "upcoming_booking", upcoming_payload)
            _log_info("Emitted dashboard_upcoming_booking (confirmed) vendor=%s bookingId=%s", vendor_id, booking_id)
    except Exception:
        _log_err("Error handling upstream booking payload")

def _connect_upstream():
    headers = {}
    if BOOKING_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {BOOKING_AUTH_TOKEN}"
    ns = _ns() or "/"
    _log_info("Connecting to upstream %s ns=%s", BOOKING_SOCKET_URL, ns)
    _upstream_sio.connect(
        BOOKING_SOCKET_URL,
        headers=headers or None,
        namespaces=[ns],   # request the correct namespace on handshake
        wait=True,
        wait_timeout=10,
        transports=["websocket", "polling"],
    )

# -----------------------------------------------------------------------------
# Upstream event handlers
# -----------------------------------------------------------------------------
def _register_upstream_handlers():
    @_upstream_sio.event
    def connect():
        _log_info("Connected to booking upstream: %s (namespace=%s)", BOOKING_SOCKET_URL, _ns() or "/")
        _mark_pong()
        _join_upstream_admin()   # always rejoin admin after connect
        with _lock:
            vendors = list(_joined_vendor_ids)
        for vid in vendors:
            _join_upstream_vendor(vid)

    @_upstream_sio.event
    def disconnect():
        _log_warn("Disconnected from booking upstream, will retry automatically")

    # Booking payload handlers (namespace-aware, server uses default namespace unless configured)
    ns = _ns()
    if ns:
        @_upstream_sio.on("booking", namespace=ns)
        def _on_booking_ns(data):
            _handle_upstream_booking(data)

        @_upstream_sio.on("booking_admin", namespace=ns)
        def _on_booking_admin_ns(data):
            _handle_upstream_booking(data)

        # Upstream health echo listener: server replies with "pong_health"
        @_upstream_sio.on("pong_health", namespace=ns)
        def _on_pong_health_ns(_data=None):
            _mark_pong()
            _log_info("Received upstream pong_health")
    else:
        @_upstream_sio.on("booking")
        def _on_booking(data):
            _handle_upstream_booking(data)

        @_upstream_sio.on("booking_admin")
        def _on_booking_admin(data):
            _handle_upstream_booking(data)

        @_upstream_sio.on("pong_health")
        def _on_pong_health(_data=None):
            _mark_pong()
            _log_info("Received upstream pong_health")

# --- helper ack callback for health pings ----------------------------------
def _on_ping_ack(data=None):
    """
    Called if the server responds by invoking the emit ack callback.
    Accepts any payload the server returned; mark pong and log it.
    """
    try:
        _mark_pong()
        _log_info("Health: ping_health ack callback received: %s", data)
    except Exception as e:
        _log_warn("Health: ping_health ack callback error: %s", e)


# -----------------------------------------------------------------------------
# Health check loop (uses ping_health)
# -----------------------------------------------------------------------------
def _health_check_loop():
    while True:
        try:
            now = time.time()
            if not _upstream_sio.connected:
                _log_warn("Health: upstream not connected; attempting connect...")
                try:
                    _connect_upstream()
                except Exception as e:
                    _log_err("Health connect failed: %s", e)
            else:
                # Re-join admin if quiet too long
                if now - _last_admin_heartbeat > _REJOIN_QUIET_SECS:
                    _log_warn("Health: quiet >%ss; rejoining admin tap", _REJOIN_QUIET_SECS)
                    _join_upstream_admin()

                # Active health ping -> expect "pong_health"
                try:
                    ns = _ns()
                    payload = {
                        "ts": now,
                        "source": "dashboard-bridge",
                        "nonce": f"{int(now*1000)}"
                    }

                    if ns:
                        _log_info("Health: ping_health payload=%s ns=%s", payload, ns)
                        # send with ack callback — server may choose to ack rather than emit pong_health
                        _upstream_sio.emit("ping_health", payload, callback=_on_ping_ack, namespace=ns)
                        _log_info("Health: sent ping_health if-branch (ns=%s, nonce=%s)", ns, payload["nonce"])
                    else:
                        _log_info("Health: ping_health payload=%s ns=/", payload)
                        _upstream_sio.emit("ping_health", payload, callback=_on_ping_ack, namespace="/")
                        _log_info("Health: sent ping_health else-branch (ns=/, nonce=%s)", payload["nonce"])
                except Exception as e:
                    _log_warn("Health: ping_health emit failed: %s", e)

                # If pong is overdue, force a reconnect to clear half-open sockets
                if now - _last_pong > max(_UPSTREAM_PING_TIMEOUT, 2 * _upstream_sio.reconnection_delay):
                    _log_warn("Health: pong overdue; forcing reconnect")
                    try:
                        _upstream_sio.disconnect()
                    except Exception:
                        pass

            time.sleep(_HEALTH_INTERVAL)
        except Exception as e:
            _log_err("Health loop crashed: %s", e)
            time.sleep(_HEALTH_INTERVAL)

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
            _connect_upstream()
            _upstream_sio.wait()
        except Exception as e:
            _log_err("Upstream bridge connection error: %s", e)

    t = threading.Thread(target=_runner, name="booking-upstream-bridge", daemon=True)
    t.start()

    hc = threading.Thread(target=_health_check_loop, name="booking-upstream-health", daemon=True)
    hc.start()

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

    # Local health check for dashboard clients
    @socketio.on("ping_health")
    def _on_ping_health(data=None):
        try:
            emit("pong_health", {"ok": True, "ts": time.time()})
        except Exception as e:
            _log_err("pong_health failed: %s", e)

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

            with _lock:
                is_new = int(vendor_id) not in _joined_vendor_ids
                if is_new:
                    _joined_vendor_ids.add(int(vendor_id))
            if is_new and _upstream_sio.connected:
                _join_upstream_vendor(int(vendor_id))
        except Exception as e:
            _log_err("dashboard_join_vendor error: %s", e)

    # Demo endpoints
    @socketio.on("slot_booked_demo")
    def handle_slot_booked(data):
        try:
            if isinstance(data, str):
                data = json.loads(data)
            current_app.logger.info("slot_booked_demo: %s", data)
            socketio.emit("slot_booked", {"slot_id": data.get("slot_id"), "status": "booked"})
        except Exception as e:
            _log_err("slot_booked_demo error: %s", e)

    @socketio.on("booking_updated_demo")
    def handle_booking_updated(data):
        try:
            current_app.logger.info("booking_updated_demo: %s", data)
            socketio.emit("booking_updated", data)
        except Exception as e:
            _log_err("booking_updated_demo error: %s", e)
