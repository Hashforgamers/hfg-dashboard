import os
import json
import logging
import threading
import time
import requests
from typing import Dict, Any, Optional, Set

from flask import current_app
from flask_socketio import SocketIO, join_room, emit
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
    cors_allowed_origins="*",
    async_mode="eventlet",  # gevent/eventlet auto if patched; falls back to threading
)

# -----------------------------------------------------------------------------
# Upstream booking service client (single persistent connection)
# -----------------------------------------------------------------------------
BOOKING_SOCKET_URL = os.getenv("BOOKING_SOCKET_URL", "wss://hfg-booking-hmnx.onrender.com")
BOOKING_HTTP_URL = os.getenv("BOOKING_HTTP_URL", "https://hfg-booking.onrender.com").rstrip("/")
BOOKING_NAMESPACE = os.getenv("BOOKING_BRIDGE_NAMESPACE")  # unset or "/" => default namespace
BOOKING_AUTH_TOKEN = os.getenv("BOOKING_AUTH_TOKEN")       # optional bearer token
DEBUG_UPSTREAM_SIO = os.getenv("DEBUG_UPSTREAM_SIO", "1") == "1"

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

def _emit_to_kiosk(kiosk_id: int, event: str, data: Dict[str, Any]):
    try:
        room = f"kiosk_{kiosk_id}"
        _log_info("Emitting %s to kiosk room %s", event, room)
        socketio.emit(event, data, room=room)
        # Compatibility room for older kiosk clients
        alt_room = f"console:{kiosk_id}"
        socketio.emit(event, data, room=alt_room)
    except Exception as e:
        _log_err("Kiosk emit failed: %s", e)


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
            _upstream_sio.wait()
        else:
            _upstream_sio.emit("connect_admin", {})
            _upstream_sio.wait()
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
    _upstream_sio.wait()

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

        @_upstream_sio.on("current_slot", namespace=ns)
        def _on_current_slot_ns(data):
            _handle_upstream_current_slot(data)

        @_upstream_sio.on("console_availability", namespace=ns)
        def _on_console_availability_ns(data):
            _handle_upstream_console_availability(data)

        # Upstream health echo listener: server replies with "pong_health"
        @_upstream_sio.on("pong_health", namespace=ns)
        def _on_pong_health_ns(_data=None):
            _mark_pong()
            _log_info("Received upstream pong_health")

        @_upstream_sio.on("pay_at_cafe_accepted", namespace=ns)
        def _on_pay_at_cafe_accepted_ns(data):
            _handle_upstream_pay_at_cafe_event("pay_at_cafe_accepted", data)

        @_upstream_sio.on("pay_at_cafe_rejected", namespace=ns)
        def _on_pay_at_cafe_rejected_ns(data):
            _handle_upstream_pay_at_cafe_event("pay_at_cafe_rejected", data)

        @_upstream_sio.on("booking_payment_update", namespace=ns)
        def _on_booking_payment_update_ns(data):
            _handle_upstream_booking_payment_update(data)
    else:
        @_upstream_sio.on("booking")
        def _on_booking(data):
            _handle_upstream_booking(data)

        @_upstream_sio.on("booking_admin")
        def _on_booking_admin(data):
            _handle_upstream_booking(data)

        @_upstream_sio.on("current_slot")
        def _on_current_slot(data):
            _handle_upstream_current_slot(data)

        @_upstream_sio.on("console_availability")
        def _on_console_availability(data):
            _handle_upstream_console_availability(data)

        @_upstream_sio.on("pong_health")
        def _on_pong_health(_data=None):
            _mark_pong()
            try:
                nonce = _data.get("nonce") if isinstance(_data, dict) else None
            except Exception:
                nonce = None
            _log_info("Received upstream pong_health (event) nonce=%s payload=%s", nonce, _data)

        @_upstream_sio.on("pay_at_cafe_accepted")
        def _on_pay_at_cafe_accepted(data):
            _handle_upstream_pay_at_cafe_event("pay_at_cafe_accepted", data)

        @_upstream_sio.on("pay_at_cafe_rejected")
        def _on_pay_at_cafe_rejected(data):
            _handle_upstream_pay_at_cafe_event("pay_at_cafe_rejected", data)

        @_upstream_sio.on("booking_payment_update")
        def _on_booking_payment_update(data):
            _handle_upstream_booking_payment_update(data)


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
                    _upstream_sio.wait()
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
                        _upstream_sio.wait()
                        _log_info("Health: sent ping_health if-branch (ns=%s, nonce=%s)", ns, payload["nonce"])
                    else:
                        _log_info("Health: ping_health payload=%s ns=/", payload)
                        _upstream_sio.emit("ping_health", payload, callback=_on_ping_ack, namespace="/")
                        _upstream_sio.wait()
                        _log_info("Health: sent ping_health else-branch (ns=/, nonce=%s)", payload["nonce"])
                except Exception as e:
                    _log_warn("Health: ping_health emit failed: %s", e)

                # If pong is overdue, force a reconnect to clear half-open sockets
                if now - _last_pong > max(_UPSTREAM_PING_TIMEOUT, 2 * _upstream_sio.reconnection_delay):
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

    @socketio.on("kiosk_join")
    def _on_kiosk_join(data: Dict[str, Any]):
        kiosk_id = data.get("kiosk_id")
        if not kiosk_id:
            _log_warn("kiosk_join missing kiosk_id")
            return
        room = f"kiosk_{kiosk_id}"
        join_room(room)
        join_room(f"console:{kiosk_id}")
        _log_info("Kiosk client joined room %s", room)


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

            socketio.emit("message", {
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
            }, room=f"console:{console_id}")

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
