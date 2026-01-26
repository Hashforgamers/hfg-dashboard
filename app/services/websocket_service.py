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
            try:
                nonce = _data.get("nonce") if isinstance(_data, dict) else None
            except Exception:
                nonce = None
            _log_info("Received upstream pong_health (event) nonce=%s payload=%s", nonce, _data)


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
        _log_info("Kiosk client joined room %s", room)


    @socketio.on("next_slot_check")
    def _on_next_slot_check(data: Any):
        try:
            # --- Handle both JSON string and dict ---
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    emit("next_slot_reply", {"type": "next_slot_reply", "ok": False, "reason": "invalid_json"})
                    return

            if not isinstance(data, dict):
                emit("next_slot_reply", {"type": "next_slot_reply", "ok": False, "reason": "invalid_format"})
                return

            # --- Extract and validate required fields ---
            vendor_id = int(data.get("vendor_id", 0))
            console_id = int(data.get("console_id", 0))
            game_id = int(data.get("game_id", 0))
            current_end = data.get("current_end_time")

            if not all([vendor_id, console_id, game_id, current_end]):
                emit("next_slot_reply", {"type": "next_slot_reply", "ok": False, "reason": "missing_fields"})
                return

            # --- Parse time (handle both UTC and IST formats) ---
            try:
                end_dt = datetime.fromisoformat(current_end.replace("Z", "+00:00"))
            except Exception:
                emit("next_slot_reply", {"type": "next_slot_reply", "ok": False, "reason": "invalid_time"})
                return

            today = end_dt.date()

            # --- Get next slot ---
            next_slot = _get_next_slot_for_today(game_id, end_dt)
            if not next_slot:
                emit("next_slot_reply", {"type": "next_slot_reply", "ok": False, "reason": "no_next_slot"})
                return

            # --- Check vendor slot availability ---
            is_avail, avail_count = _vendor_slot_availability(vendor_id, next_slot.id, today)
            if is_avail is None:
                emit("next_slot_reply", {"type": "next_slot_reply", "ok": False, "reason": "slot_row_missing"})
                return

            # --- Get price ---
            price_row = db.session.execute(
                text("SELECT single_slot_price FROM available_games WHERE id = :gid"),
                {"gid": game_id}
            ).fetchone()
            price = int(price_row.single_slot_price) if price_row and price_row.single_slot_price is not None else None

            # --- Build candidate slot info ---
            candidate_start = end_dt
            candidate_end = end_dt.replace(
                hour=next_slot.end_time.hour,
                minute=next_slot.end_time.minute,
                second=0,
                microsecond=0,
            )

            # --- Send response ---
            emit("next_slot_reply", {
                "type": "next_slot_reply",
                "ok": bool(is_avail and avail_count > 0),
                "reason": None if (is_avail and avail_count > 0) else "unavailable",
                "vendor_id": vendor_id,
                "console_id": console_id,
                "game_id": game_id,
                "current_booking_id": int(data.get("current_booking_id")) if data.get("current_booking_id") else None,
                "candidate": {
                    "slot_id": next_slot.id,
                    "start_time": _iso(candidate_start),
                    "end_time": _iso(candidate_end),
                    "available": bool(is_avail),
                    "available_count": avail_count,
                    "price": price
                }
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
            vendor_id = int(data["vendor_id"]); console_id = int(data["console_id"])
            game_id = int(data["game_id"]); curr_booking_id = int(data["current_booking_id"])
            start_dt = datetime.fromisoformat(data["start_time"].replace("Z","+00:00"))
            end_dt = datetime.fromisoformat(data["end_time"].replace("Z","+00:00"))
            slot_id = int(data.get("slot_id")) if data.get("slot_id") else None

            # Validate schedule and resolve slot_id if not provided
            next_slot = _get_next_slot_for_today(game_id, start_dt)
            if not next_slot or next_slot.end_time != end_dt.time():
                emit("next_slot_error", {"type":"next_slot_error","reason":"invalid_candidate"}); return
            if slot_id is None:
                slot_id = next_slot.id

            vendor_slot_table = f"VENDOR_{vendor_id}_SLOT"
            today = start_dt.date()

            # 1) Lock vendor slot row and ensure availability
            row = db.session.execute(text(f"""
                SELECT is_available, available_slot
                FROM {vendor_slot_table}
                WHERE vendor_id=:vid AND date=:dt AND slot_id=:sid
                FOR UPDATE
            """), {"vid": vendor_id, "dt": today, "sid": slot_id}).mappings().first()
            if not row:
                emit("next_slot_error", {"type":"next_slot_error","reason":"slot_row_missing"}); db.session.rollback(); return
            if not row["is_available"] or int(row["available_slot"]) <= 0:
                emit("next_slot_error", {"type":"next_slot_error","reason":"unavailable"}); db.session.rollback(); return

            # 2) Decrement available_slot
            db.session.execute(text(f"""
                UPDATE {vendor_slot_table}
                SET available_slot = available_slot - 1,
                    is_available = CASE WHEN available_slot - 1 > 0 THEN TRUE ELSE FALSE END
                WHERE vendor_id=:vid AND date=:dt AND slot_id=:sid
            """), {"vid": vendor_id, "dt": today, "sid": slot_id})

            # 3) Lock console row and ensure it can be occupied for next hour (optional)
            console_table = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
            row2 = db.session.execute(text(f"""
                SELECT is_available FROM {console_table}
                WHERE console_id=:cid AND game_id=:gid
                FOR UPDATE
            """), {"cid": console_id, "gid": game_id}).first()
            # Not strictly needed if availability table reflects only current hour

            # 4) Create provisional booking and dashboard record (pending payment)
            session_id = f"sess-{curr_booking_id}"
            seg = str(uuid.uuid4())
            booking = Booking(user_id=None, vendor_id=vendor_id, game_id=game_id, slot_id=slot_id)
            db.session.add(booking)
            db.session.flush()
            new_book_id = booking.id

            booking_table = f"VENDOR_{vendor_id}_DASHBOARD"
            db.session.execute(text(f"""
                INSERT INTO {booking_table}
                    (book_id, game_id, date, start_time, end_time, book_status, console_id, payment_status, session_id, segment_id)
                VALUES
                    (:bid, :gid, :dt, :st, :et, 'upcoming', NULL, 'pending', :sid, :seg)
            """), {"bid": new_book_id, "gid": game_id, "dt": today, "st": start_dt, "et": end_dt, "sid": session_id, "seg": seg})

            # 5) Occupy console and flip to current
            db.session.execute(text(f"""
                UPDATE {console_table} SET is_available = FALSE
                WHERE console_id=:cid AND game_id=:gid
            """), {"cid": console_id, "gid": game_id})

            db.session.execute(text(f"""
                UPDATE {booking_table}
                SET book_status='current', console_id=:cid
                WHERE book_id=:bid AND game_id=:gid AND start_time=:st AND end_time=:et
            """), {"cid": console_id, "bid": new_book_id, "gid": game_id, "st": start_dt, "et": end_dt})

            db.session.commit()

            # 6) Notify kiosk and vendor
            socketio.emit("message", {
                "type":"extend_confirm","console_id": console_id,
                "data":{"booking_id": new_book_id, "new_end_time": _iso(end_dt), "provisional": True}
            }, room=f"console:{console_id}")

            socketio.emit("extend_confirm", {
                "vendorId": vendor_id, "console_id": console_id,
                "booking_id": new_book_id, "new_end_time": _iso(end_dt), "provisional": True
            }, room=f"vendor_{vendor_id}")

            emit("next_slot_confirm", {
                "type":"next_slot_confirm","booking_id": new_book_id,
                "console_id": console_id,"new_end_time": _iso(end_dt),
                "provisional": True, "slot_id": slot_id
            })
        except Exception:
            db.session.rollback()
            current_app.logger.exception("next_slot_book error")
            emit("next_slot_error", {"type":"next_slot_error","reason":"server_error"})
