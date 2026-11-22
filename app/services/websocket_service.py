from app.services.kiosk_security import linked_identity, vendor_identity, KioskError
import os
import json
import logging
import threading
import time
import requests
from typing import Dict, Any, Optional, Set

from flask import current_app, session, g
from flask_socketio import SocketIO, join_room, leave_room, emit, disconnect
import socketio as pwsio   # python-socketio client (aliased)
from app.services.payload_formatters import format_upcoming_booking_from_upstream
from datetime import datetime, timedelta, timezone as dt_timezone
from datetime import time as dt_time
from sqlalchemy import text
import uuid

from app.extension.extensions import db
from app.models.slot import Slot
from app.models.booking import Booking


# -----------------------------------------------------------------------------
# Dashboard Socket.IO server (clients connect here)
# -----------------------------------------------------------------------------
socketio = SocketIO(
    cors_allowed_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*"),
    async_mode="eventlet",  # gevent/eventlet auto if patched; falls back to threading
    ping_interval=int(os.getenv("SOCKETIO_PING_INTERVAL_SEC", "25") or 25),
    ping_timeout=int(os.getenv("SOCKETIO_PING_TIMEOUT_SEC", "60") or 60),
    max_http_buffer_size=int(os.getenv("SOCKETIO_MAX_HTTP_BUFFER_BYTES", str(1_000_000)) or 1_000_000),
)

# -----------------------------------------------------------------------------
# Upstream booking service client (single persistent connection)
# -----------------------------------------------------------------------------
BOOKING_SOCKET_URL = os.getenv("BOOKING_SOCKET_URL", "wss://hfg-booking-hmnx.onrender.com")
BOOKING_HTTP_URL = os.getenv("BOOKING_HTTP_URL", "https://hfg-booking.onrender.com").rstrip("/")
BOOKING_NAMESPACE = os.getenv("BOOKING_BRIDGE_NAMESPACE")  # unset or "/" => default namespace
BOOKING_AUTH_TOKEN = os.getenv("BOOKING_AUTH_TOKEN")       # optional bearer token
DEBUG_UPSTREAM_SIO = os.getenv("DEBUG_UPSTREAM_SIO", "0") == "1"

_upstream_sio = pwsio.Client(
    reconnection=True,
    reconnection_attempts=0,
    reconnection_delay=1.0,
    reconnection_delay_max=10.0,
    logger=DEBUG_UPSTREAM_SIO,
    engineio_logger=DEBUG_UPSTREAM_SIO,
)

_started_upstream = False
_joined_vendor_ids: Set[int] = set()
_lock = threading.Lock()

_last_forced_reconnect = 0.0
_RECONNECT_BACKOFF = 5.0   

# Upstream callbacks run on the socket client's thread, outside any request.
_bridge_app = None

# hfg-booking sends most booking changes twice (vendor room + admin tap, and
# some paths emit "booking" to both). Relay each change to the dashboard once.
_recent_upstream: Dict[tuple, float] = {}
_DEDUPE_WINDOW_SECS = 5.0

# Heartbeat tracking
_last_admin_heartbeat = 0.0
_last_pong = 0.0
_UPSTREAM_PING_TIMEOUT = 20.0  # seconds to consider pong overdue
_HEALTH_INTERVAL = 20          # seconds between health checks
_REJOIN_QUIET_SECS = 60        # if no traffic for this long, re-join admin

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _vendor_slot_availability(vendor_id: int, slot_id: int, on_date: datetime.date):
    table = f"VENDOR_{vendor_id}_SLOT"
    row = db.session.execute(text(f"""
        SELECT is_available, available_slot
        FROM {table}
        WHERE vendor_id = :vid AND date = :dt AND slot_id = :sid
    """), {"vid": vendor_id, "dt": on_date, "sid": slot_id}).mappings().first()
    if not row:
        return None, None
    return bool(row["is_available"]), int(row["available_slot"])


def _get_next_slot_for_today(game_id: int, current_end_dt: datetime):
    next_slot = (db.session.query(Slot)
                 .filter(Slot.gaming_type_id == int(game_id),
                         Slot.start_time == current_end_dt.time())
                 .order_by(Slot.start_time.asc())
                 .first())
    return next_slot

def _iso(dt):
    return dt.astimezone(dt_timezone.utc).isoformat().replace("+00:00","Z")

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

def _seen_recently(key: tuple) -> bool:
    """True when the same upstream change was already relayed moments ago."""
    now = time.time()
    with _lock:
        for k, ts in list(_recent_upstream.items()):
            if now - ts > _DEDUPE_WINDOW_SECS:
                _recent_upstream.pop(k, None)
        if key in _recent_upstream:
            return True
        _recent_upstream[key] = now
        return False


def _run_in_app(fn, *args):
    """Run DB work from an upstream callback inside the Flask app context."""
    app = _bridge_app
    if app is None:
        return None
    with app.app_context():
        try:
            return fn(*args)
        finally:
            try:
                db.session.remove()
            except Exception:
                pass


def _booking_consoles(vendor_id: int, booking_id: int, hinted: Optional[int]):
    table = f"VENDOR_{int(vendor_id)}_DASHBOARD"
    row = db.session.execute(text(f"""
        SELECT d.console_id, d.book_status, b.squad_details
        FROM {table} d JOIN bookings b ON b.id = d.book_id
        WHERE d.book_id = :bid
    """), {"bid": int(booking_id)}).mappings().first()
    if not row or str(row["book_status"] or "").lower() != "current":
        return []
    from app.services.kiosk_runtime import assigned_consoles
    consoles = assigned_consoles(row)
    if not consoles and hinted and hinted > 0:
        consoles = {int(hinted)}
    return sorted(consoles)


def _unlock_started_booking(vendor_id, booking_id, console_id=None):
    """A booking that hfg-booking started (desk walk-in, kiosk continuation)
    must unlock its PC the same way a dashboard start does. The kiosk only
    listens to this service, so without this it stayed locked until staff
    pressed Start again. Unlock-only: an idle console is never locked here."""
    try:
        vendor_id = int(vendor_id or 0)
        booking_id = int(booking_id or 0)
        hinted = int(console_id or 0)
    except (TypeError, ValueError):
        return
    if vendor_id <= 0 or booking_id <= 0:
        return
    if _seen_recently(("unlock", vendor_id, booking_id)):
        return

    def work():
        consoles = _booking_consoles(vendor_id, booking_id, hinted)
        db.session.rollback()
        if not consoles:
            return
        from app.services.kiosk_runtime import notify_console_runtime
        notify_console_runtime(vendor_id, consoles, unlock_only=True)

    try:
        _run_in_app(work)
    except Exception:
        _log_err("Kiosk unlock for upstream booking failed vendor=%s booking=%s", vendor_id, booking_id)


# -----------------------------------------------------------------------------
# Downstream emit (to dashboard clients)
# -----------------------------------------------------------------------------
def _emit_downstream_to_vendor(vendor_id: Optional[int], event: str, data: Dict[str, Any]):
    try:
        if vendor_id is not None:
            # The snapshot endpoints use short in-process caches. Invalidate before
            # notifying clients so an immediate refresh cannot replay pre-event data.
            if event in {"booking", "upcoming_booking", "current_slot", "console_availability", "booking_payment_update", "pay_at_cafe_accepted", "pay_at_cafe_rejected", "kiosk_session_extended", "booking_updated"}:
                try:
                    from app.routes import _invalidate_vendor_caches
                    _invalidate_vendor_caches(int(vendor_id))
                except Exception:
                    _log_err("Cache invalidation failed vendor=%s", vendor_id)
            room = f"vendor_{int(vendor_id)}"
            _log_info("Emitting %s to %s", event, room)
            socketio.emit(event, data, room=room)
        else:
            _log_info("Emitting %s to broadcast", event)
            socketio.emit(event, data, broadcast=True)
    except Exception:
        _log_err("Downstream emit failed event=%s vendor=%s", event, vendor_id)

def _emit_to_kiosk(kiosk_id: int, event: str, data: Dict[str, Any]):
    # Starts publish once after commit; a revoked link never receives new events.
    if getattr(g, "kiosk_transaction", False):
        return
    try:
        rows = db.session.execute(text("SELECT id FROM console_link_sessions WHERE console_id=:cid AND status='active'"), {"cid": int(kiosk_id)}).fetchall()
        for row in rows:
            socketio.emit(event, data, room=f"kiosk_link_{row.id}")
    except Exception:
        _log_err("Kiosk emit failed console=%s", kiosk_id)
    # A paired Console Lock TV receives the same decision via its own contract.
    try:
        from app.services.console_tv import on_legacy_kiosk_event
        on_legacy_kiosk_event(kiosk_id, event, data)
    except Exception:
        _log_err("Console TV bridge failed console=%s", kiosk_id)


def _console_tv_call(fn):
    try:
        from app.services import console_tv
        link = console_tv.link_for_identity(_socket_identity())
        return dict(fn(link, console_tv), ok=True)
    except KioskError as exc:
        db.session.rollback()
        return {"ok": False, "code": exc.error_code}
    except Exception:
        db.session.rollback()
        _log_err("Console TV socket event failed")
        return {"ok": False, "code": "internal_error"}


def _socket_identity():
    identity = session.get("socket_identity")
    if not identity:
        raise KioskError("token_required")
    if identity["kind"] == "kiosk":
        active = db.session.execute(text("SELECT 1 FROM console_link_sessions WHERE id=:id AND status='active'"), {"id": identity["id"]}).first()
        if not active:
            raise KioskError("invalid_session_token")
    else:
        identity = vendor_identity(session.get("socket_token"), permission="dashboard.view")
    return identity


def _socket_console_scope(data):
    identity = _socket_identity()
    if identity['kind'] != 'kiosk':
        raise KioskError('kiosk_token_required', 403)
    if int(data.get('console_id') or 0) != identity['console_id'] or int(data.get('vendor_id') or 0) != identity['vendor_id']:
        raise KioskError('console_mismatch', 403)
    # Bind continuation requests to a running booking belonging to this device.
    from app.services.kiosk_runtime import booking_window
    booking_id = data.get('current_booking_id') or data.get('currentBookingId') or data.get('booking_id')
    window = booking_window(identity['vendor_id'], booking_id, identity['console_id'])
    if window['status'] != 'active':
        raise KioskError('session_ended', 409)
    data['user_id'] = window['user_id']
    data['game_id'] = window['game_id']
    return identity


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
        if booking_id and _seen_recently(("booking", str(vendor_id), str(booking_id),
                                          str(data.get("status")), str(data.get("booking_status")))):
            return
        _log_info("[Upstream booking] vendor=%s bookingId=%s", vendor_id, booking_id)

        # Always relay raw event for general consumers
        _emit_downstream_to_vendor(vendor_id, "booking", data)
        try:
            _emit_downstream_to_vendor(
                vendor_id,
                "booking_updated",
                {
                    "vendor_id": vendor_id,
                    "booking_id": booking_id,
                    "slot_id": data.get("slotId") or data.get("slot_id"),
                    "booked_date": data.get("date"),
                    "status": data.get("status"),
                    "event": "booking",
                },
            )
        except Exception:
            _log_warn("Failed emitting booking_updated vendor=%s bookingId=%s", vendor_id, booking_id)
        try:
            _emit_downstream_to_vendor(
                vendor_id,
                "booking_slots_updated",
                {
                    "vendor_id": vendor_id,
                    "booking_id": booking_id,
                    "slot_id": data.get("slotId") or data.get("slot_id"),
                    "booked_date": data.get("date"),
                    "status": data.get("status"),
                    "event": "booking",
                },
            )
        except Exception:
            _log_warn("Failed emitting booking_slots_updated vendor=%s bookingId=%s", vendor_id, booking_id)

        # Emit upcoming for confirmed bookings
        upcoming_payload = format_upcoming_booking_from_upstream(data)
        if upcoming_payload:
            _emit_downstream_to_vendor(vendor_id, "upcoming_booking", upcoming_payload)
            _log_info("Emitted dashboard_upcoming_booking (confirmed) vendor=%s bookingId=%s", vendor_id, booking_id)
    except Exception:
        _log_err("Error handling upstream booking payload")


def _handle_upstream_current_slot(data: Dict[str, Any]):
    try:
        _mark_pong()
        vendor_id = data.get("vendorId") or data.get("vendor_id")
        _emit_downstream_to_vendor(vendor_id, "current_slot", data)
        try:
            _emit_downstream_to_vendor(
                vendor_id,
                "booking_slots_updated",
                {
                    "vendor_id": vendor_id,
                    "booking_id": data.get("bookingId") or data.get("booking_id") or data.get("bookId") or data.get("book_id"),
                    "slot_id": data.get("slotId") or data.get("slot_id"),
                    "booked_date": data.get("date"),
                    "status": data.get("status"),
                    "event": "current_slot",
                },
            )
        except Exception:
            _log_warn("Failed emitting booking_slots_updated for current_slot vendor=%s", vendor_id)
        _log_info("Relayed current_slot vendor=%s bookingId=%s", vendor_id, data.get("bookingId") or data.get("book_id"))
        _unlock_started_booking(
            vendor_id,
            data.get("bookingId") or data.get("booking_id") or data.get("bookId") or data.get("book_id"),
            data.get("console_id") or data.get("consoleId"),
        )
    except Exception:
        _log_err("Error handling upstream current_slot payload")


def _handle_upstream_console_availability(data: Dict[str, Any]):
    try:
        _mark_pong()
        vendor_id = data.get("vendorId") or data.get("vendor_id")
        _emit_downstream_to_vendor(vendor_id, "console_availability", data)
        _log_info(
            "Relayed console_availability vendor=%s console_id=%s is_available=%s",
            vendor_id, data.get("console_id"), data.get("is_available")
        )
    except Exception:
        _log_err("Error handling upstream console_availability payload")


def _handle_upstream_pay_at_cafe_event(event: str, data: Dict[str, Any]):
    try:
        _mark_pong()
        vendor_id = data.get("vendorId") or data.get("vendor_id")
        _emit_downstream_to_vendor(vendor_id, event, data)
        try:
            _emit_downstream_to_vendor(
                vendor_id,
                "booking_queue_updated",
                {
                    "vendor_id": vendor_id,
                    "booking_id": data.get("bookingId") or data.get("booking_id"),
                    "status": data.get("status"),
                    "event": event,
                },
            )
        except Exception:
            _log_warn("Failed emitting booking_queue_updated vendor=%s event=%s", vendor_id, event)
        _log_info("Relayed %s vendor=%s bookingId=%s", event, vendor_id, data.get("bookingId"))
    except Exception:
        _log_err("Error handling upstream %s payload", event)

def _handle_upstream_booking_payment_update(data: Dict[str, Any]):
    try:
        _mark_pong()
        vendor_id = data.get("vendorId") or data.get("vendor_id")
        _emit_downstream_to_vendor(vendor_id, "booking_payment_update", data)
        try:
            _emit_downstream_to_vendor(
                vendor_id,
                "booking_queue_updated",
                {
                    "vendor_id": vendor_id,
                    "booking_id": data.get("bookingId") or data.get("booking_id"),
                    "status": data.get("status"),
                    "event": "booking_payment_update",
                },
            )
        except Exception:
            _log_warn("Failed emitting booking_queue_updated vendor=%s bookingId=%s", vendor_id, data.get("bookingId"))
        _log_info("Relayed booking_payment_update vendor=%s bookingId=%s", vendor_id, data.get("bookingId"))
    except Exception:
        _log_err("Error handling upstream booking_payment_update payload")

def _handle_upstream_kiosk_session_extended(data: Dict[str, Any]):
    try:
        _mark_pong()
        vendor_id = data.get("vendorId") or data.get("vendor_id")
        _emit_downstream_to_vendor(vendor_id, "kiosk_session_extended", data)
        _emit_downstream_to_vendor(vendor_id, "booking_slots_updated", {
            "vendor_id": vendor_id,
            "booking_id": data.get("booking_id"),
            "slot_id": data.get("slot_id"),
            "status": data.get("book_status"),
            "event": "kiosk_session_extended",
        })
        if data.get("auto_started"):
            _unlock_started_booking(vendor_id, data.get("booking_id"), data.get("console_id"))
    except Exception:
        _log_err("Error handling upstream kiosk_session_extended payload")


def _relay_upstream(event: str):
    """Relay a vendor-scoped upstream event to the dashboard unchanged."""
    def handler(data=None):
        try:
            _mark_pong()
            data = data if isinstance(data, dict) else {}
            _emit_downstream_to_vendor(data.get("vendorId") or data.get("vendor_id"), event, data)
        except Exception:
            _log_err("Error relaying upstream %s", event)
    return handler


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

    def _on_pong_health(_data=None):
        _mark_pong()

    handlers = {
        "booking": _handle_upstream_booking,
        "booking_admin": _handle_upstream_booking,
        "current_slot": _handle_upstream_current_slot,
        "console_availability": _handle_upstream_console_availability,
        "pong_health": _on_pong_health,
        "pay_at_cafe_accepted": lambda data: _handle_upstream_pay_at_cafe_event("pay_at_cafe_accepted", data),
        "pay_at_cafe_rejected": lambda data: _handle_upstream_pay_at_cafe_event("pay_at_cafe_rejected", data),
        "booking_payment_update": _handle_upstream_booking_payment_update,
        # Previously emitted by hfg-booking but never relayed:
        "kiosk_session_extended": _handle_upstream_kiosk_session_extended,
        "booking_updated": _relay_upstream("booking_updated"),
        "gamers_credit_updated": _relay_upstream("gamers_credit_updated"),
    }
    for event, handler in handlers.items():
        _upstream_sio.on(event, handler, namespace=ns or "/")


# --- helper ack callback for health pings ----------------------------------
def _on_ping_ack(data=None):
    try:
        _mark_pong()
        nonce = None
        try:
            nonce = data.get("nonce") if isinstance(data, dict) else None
        except Exception:
            nonce = None
        _log_info("Health: ping_health ack callback received (nonce=%s) payload=%s", nonce, data)
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
                if now - _last_pong > max(_UPSTREAM_PING_TIMEOUT, 3 * _HEALTH_INTERVAL):
                    # rate-limit forced reconnects to avoid flapping
                    global _last_forced_reconnect
                    if now - _last_forced_reconnect < _RECONNECT_BACKOFF:
                        _log_warn("Health: pong overdue but recently forced reconnect; skipping")
                    else:
                        _log_warn("Health: pong overdue; forcing reconnect")
                        _last_forced_reconnect = now
                        try:
                            # disconnect then short sleep to let the socket fully close before reconnect attempts happen
                            _upstream_sio.disconnect()
                            time.sleep(1.0)
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
    global _started_upstream, _bridge_app
    with _lock:
        if _started_upstream:
            return
        _started_upstream = True
    if app is not None:
        _bridge_app = app

    _register_upstream_handlers()

    # One supervisor owns connection attempts. Socket.IO runs its own receive loop;
    # wait() here or in an event callback blocks rejoin and heartbeat processing.
    hc = threading.Thread(target=_health_check_loop, name="booking-upstream-health", daemon=True)
    hc.start()

# -----------------------------------------------------------------------------
# Dashboard (local) socket events
# -----------------------------------------------------------------------------
def register_dashboard_events():
    @socketio.on("connect")
    def _on_connect(auth=None):
        try:
            if not isinstance(auth, dict):
                return False
            if auth.get("session_token"):
                identity = linked_identity(auth["session_token"])
                claimed = auth.get("console_id")
                if claimed is not None and int(claimed) != identity["console_id"]:
                    return False
                tv_device = False
                try:
                    from app.services.console_tv import device_type_of
                    tv_device = device_type_of(identity["id"]) == "CONSOLE_TV"
                except Exception:
                    db.session.rollback()
                if tv_device:
                    # Console Lock TVs get only the versioned device contract.
                    identity["device_type"] = "CONSOLE_TV"
                    join_room(f"device_{identity['id']}")
                else:
                    join_room(f"kiosk_link_{identity['id']}")
            else:
                identity = vendor_identity(auth.get("token"), permission="dashboard.view")
                session["socket_token"] = auth.get("token")
            session["socket_identity"] = identity
        except (KioskError, ValueError, TypeError):
            return False

    @socketio.on("disconnect")
    def _on_disconnect(reason=None):
        _log_info("Dashboard client disconnected")
        identity = session.get("socket_identity") or {}
        if identity.get("device_type") == "CONSOLE_TV":
            from app.services.console_tv import record_disconnect
            record_disconnect(identity)

    # Console Lock TV -> server. Each handler re-validates the link and
    # returns an acknowledgement payload (Socket.IO callback).
    @socketio.on("device.heartbeat")
    def _on_device_heartbeat(data=None):
        return _console_tv_call(lambda link, tv: tv.heartbeat(link, data if isinstance(data, dict) else {}))

    @socketio.on("device.control.result")
    def _on_device_control_result(data=None):
        def record(link, tv):
            result, follow_up = tv.record_result(link, data if isinstance(data, dict) else {})
            db.session.commit()
            if follow_up:
                tv.publish([(link, [(c["type"], c) for c in follow_up])])
            tv.notify_vendor(link, "command_result")
            return dict(result, followUpCommands=follow_up)
        return _console_tv_call(record)

    # Local health check for dashboard clients
    @socketio.on("ping_health")
    def _on_ping_health(data=None):
        try:
            _socket_identity()
            emit("pong_health", {"ok": True, "ts": time.time()})
        except Exception as e:
            _log_err("pong_health failed: %s", e)

    @socketio.on("dashboard_leave_vendor")
    def _on_dashboard_leave_vendor(data):
        vendor_id = (data or {}).get("vendor_id")
        if vendor_id:
            leave_room(f"vendor_{int(vendor_id)}")

    @socketio.on("dashboard_join_vendor")
    def _on_dashboard_join_vendor(data: Dict[str, Any]):
        try:
            identity = _socket_identity()
            vendor_id = data.get("vendor_id") or data.get("vendorId")
            if identity["kind"] != "vendor" or int(vendor_id or 0) != identity["vendor_id"]:
                disconnect()
                return
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

    @socketio.on("booking_accepted")
    def _on_booking_accepted(data=None):
        # NotificationPanel emits this after accepting; share it with the
        # vendor's other open dashboards (upcoming-booking listens for it).
        try:
            identity = _socket_identity()
            data = data if isinstance(data, dict) else {}
            vendor_id = int(data.get("vendorId") or data.get("vendor_id") or 0)
            if identity["kind"] != "vendor" or vendor_id != identity["vendor_id"]:
                return
            socketio.emit("booking_accepted", data, room=f"vendor_{vendor_id}", include_self=False)
        except Exception as e:
            _log_warn("booking_accepted relay failed: %s", e)

    @socketio.on("kiosk_join")
    def _on_kiosk_join(data=None):
        try:
            identity = _socket_identity()
            if identity["kind"] != "kiosk":
                raise KioskError("kiosk_token_required")
            data = data or {}
            claimed = data.get("console_id", data.get("kiosk_id"))
            if claimed is not None and int(claimed) != identity["console_id"]:
                raise KioskError("console_mismatch", 403)
            if identity.get("device_type") == "CONSOLE_TV":
                join_room(f"device_{identity['id']}")
            else:
                join_room(f"kiosk_link_{identity['id']}")
        except (KioskError, ValueError, TypeError):
            disconnect()

    @socketio.on("next_slot_check")
    def _on_next_slot_check(data: Any):
        try:
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    emit("next_slot_reply", {"type": "next_slot_reply", "ok": False, "reason": "invalid_json"})
                    return

            if not isinstance(data, dict):
                emit("next_slot_reply", {"type": "next_slot_reply", "ok": False, "reason": "invalid_format"})
                return

            _socket_console_scope(data)
            vendor_id = int(data.get("vendor_id", 0) or 0)
            console_id = int(data.get("console_id", 0) or 0)
            if not vendor_id or not console_id:
                emit("next_slot_reply", {"type": "next_slot_reply", "ok": False, "reason": "missing_fields"})
                return

            payload = {
                "current_booking_id": data.get("current_booking_id") or data.get("currentBookingId") or data.get("booking_id"),
                "console_id": console_id,
                "game_id": data.get("game_id") or data.get("gameId"),
                "user_id": data.get("user_id") or data.get("userId"),
            }
            if data.get("access_code") or data.get("accessCode"):
                payload["access_code"] = data.get("access_code") or data.get("accessCode")

            resp = requests.post(
                f"{BOOKING_HTTP_URL}/api/kiosk/next-slot/check/vendor/{vendor_id}",
                json=payload,
                timeout=4,
            )
            try:
                body = resp.json()
            except Exception:
                body = {"success": False, "message": resp.text}

            can_extend = bool(body.get("can_extend"))
            emit("next_slot_reply", {
                "type": "next_slot_reply",
                "ok": bool(body.get("success") and can_extend),
                "vendor_id": vendor_id,
                "console_id": console_id,
                "game_id": int(payload["game_id"]) if payload.get("game_id") else None,
                "current_booking_id": int(payload["current_booking_id"]) if payload.get("current_booking_id") else None,
                "can_extend": can_extend,
                "candidate": body.get("candidate"),
                "message": body.get("message"),
                "reason": None if can_extend else (body.get("message") or "unavailable"),
                "upstream_status": int(resp.status_code),
            })

        except Exception as e:
            current_app.logger.exception("next_slot_check error")
            emit("next_slot_reply", {
                "type": "next_slot_reply",
                "ok": False,
                "reason": "server_error",
                "detail": str(e)
            })

    @socketio.on("next_slot_book")
    def _on_next_slot_book(data: Dict[str, Any]):
        try:
            if isinstance(data, str):
                data = json.loads(data)
            if not isinstance(data, dict):
                emit("next_slot_error", {"type": "next_slot_error", "reason": "invalid_format"})
                return

            _socket_console_scope(data)
            vendor_id = int(data.get("vendor_id", 0) or 0)
            console_id = int(data.get("console_id", 0) or 0)
            if not vendor_id or not console_id:
                emit("next_slot_error", {"type": "next_slot_error", "reason": "missing_fields"})
                return

            payload = {
                "current_booking_id": data.get("current_booking_id") or data.get("currentBookingId") or data.get("booking_id"),
                "console_id": console_id,
                "game_id": data.get("game_id") or data.get("gameId"),
                "user_id": data.get("user_id") or data.get("userId"),
                "slot_id": data.get("slot_id") or data.get("slotId"),
                "paymentType": data.get("paymentType") or "pending",
                "autoStart": bool(data.get("autoStart", True)),
                "kioskId": data.get("kioskId") or data.get("kiosk_id"),
            }
            if data.get("access_code") or data.get("accessCode"):
                payload["access_code"] = data.get("access_code") or data.get("accessCode")

            resp = requests.post(
                f"{BOOKING_HTTP_URL}/api/kiosk/next-slot/vendor/{vendor_id}",
                json=payload,
                timeout=6,
            )
            try:
                body = resp.json()
            except Exception:
                body = {"success": False, "message": resp.text}

            if resp.status_code >= 400 or not body.get("success"):
                emit("next_slot_error", {
                    "type": "next_slot_error",
                    "reason": "upstream_failed",
                    "message": body.get("message"),
                    "detail": body.get("error"),
                    "status_code": int(resp.status_code),
                })
                return

            booking_id = int(body.get("booking_id"))
            slot_id = int(body.get("slot_id")) if body.get("slot_id") is not None else None
            end_time_ist = body.get("end_time_ist")
            book_status = body.get("book_status")

            _emit_to_kiosk(console_id, "message", {
                "type": "extend_confirm",
                "console_id": console_id,
                "data": {
                    "booking_id": booking_id,
                    "new_end_time_ist": end_time_ist,
                    "slot_id": slot_id,
                    "book_status": book_status,
                    "settlement_status": body.get("settlement_status"),
                    "amount_due": body.get("amount_due"),
                    "auto_started": body.get("auto_started"),
                },
            })

            socketio.emit("extend_confirm", {
                "vendorId": vendor_id,
                "console_id": console_id,
                "booking_id": booking_id,
                "new_end_time_ist": end_time_ist,
                "slot_id": slot_id,
                "book_status": book_status,
                "settlement_status": body.get("settlement_status"),
                "amount_due": body.get("amount_due"),
                "auto_started": body.get("auto_started"),
            }, room=f"vendor_{vendor_id}")

            emit("next_slot_confirm", {
                "type": "next_slot_confirm",
                "success": True,
                "booking_id": booking_id,
                "console_id": console_id,
                "slot_id": slot_id,
                "new_end_time_ist": end_time_ist,
                "book_status": book_status,
                "settlement_status": body.get("settlement_status"),
                "amount_due": body.get("amount_due"),
                "auto_started": body.get("auto_started"),
            })
        except Exception:
            current_app.logger.exception("next_slot_book error")
            emit("next_slot_error", {"type":"next_slot_error","reason":"server_error"})
