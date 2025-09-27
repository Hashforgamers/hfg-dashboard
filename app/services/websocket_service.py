# app/services/websocket_service.py
import os
import json
import logging
import threading
import time
from typing import Dict, Any, Optional, Set

from flask import current_app
from flask_socketio import SocketIO, join_room
import socketio as pwsio   # python-socketio client (aliased)
from app.services.payload_formatters import format_upcoming_booking_from_upstream

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
BOOKING_SOCKET_URL = os.getenv("BOOKING_SOCKET_URL", "https://hfg-booking-hmnx.onrender.com")
BOOKING_NAMESPACE = os.getenv("BOOKING_BRIDGE_NAMESPACE")  # keep unset for default "/"
BOOKING_AUTH_TOKEN = os.getenv("BOOKING_AUTH_TOKEN")       # optional bearer token

# In websocket_service.py - Enhanced client configuration
_upstream_sio = pwsio.Client(
    reconnection=True,
    reconnection_attempts=0,          # infinite attempts
    reconnection_delay=2.0,           # start with 2 seconds
    reconnection_delay_max=30.0,      # max 30 seconds between attempts
    #max_reconnection_attempts=0,      # infinite
    randomization_factor=0.5,
    logger=True,                      # enable for debugging
    engineio_logger=True,
)


_started_upstream = False
_joined_vendor_ids: Set[int] = set()
_lock = threading.Lock()
_last_admin_heartbeat = 0

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
        
        
        # Add this function after _join_upstream_admin()
def _connect_with_retry():
    """Connect with retry logic and proper error handling"""
    max_initial_attempts = 5
    attempt = 0
    
    while attempt < max_initial_attempts:
        try:
            kwargs = {
                'transports': ['websocket', 'polling'],  # Allow fallback
                'wait_timeout': 20,  # ✅ Correct parameter name (not 'timeout')
            }
            
            if BOOKING_AUTH_TOKEN:
                kwargs["headers"] = {"Authorization": f"Bearer {BOOKING_AUTH_TOKEN}"}
                
            _upstream_sio.connect(BOOKING_SOCKET_URL, **kwargs)
            _log_info("Successfully connected to booking service")
            return True
            
        except Exception as e:
            attempt += 1
            _log_err("Connection attempt %d failed: %s", attempt, e)
            if attempt < max_initial_attempts:
                time.sleep(2 ** attempt)  # exponential backoff
    
    return False




def _handle_upstream_booking(data: Dict[str, Any]):
    global _last_admin_heartbeat
    try:
        _last_admin_heartbeat = time.time()  # mark heartbeat
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

# -----------------------------------------------------------------------------
# Upstream event handlers
# -----------------------------------------------------------------------------
def _register_upstream_handlers():
    @_upstream_sio.event
    def connect():
        _log_info("Connected to booking upstream: %s (namespace=%s)", BOOKING_SOCKET_URL, BOOKING_NAMESPACE or "/")
        _join_upstream_admin()   # always rejoin admin
        with _lock:
            vendors = list(_joined_vendor_ids)
        for vid in vendors:
            _join_upstream_vendor(vid)

    @_upstream_sio.event
    def disconnect():
        _log_warn("Disconnected from booking upstream, will retry automatically")

    if BOOKING_NAMESPACE:
        @_upstream_sio.on("booking", namespace=BOOKING_NAMESPACE)
        def _on_booking_ns(data):
            _handle_upstream_booking(data)
    else:
        @_upstream_sio.on("booking")
        def _on_booking(data):
            _handle_upstream_booking(data)

    if BOOKING_NAMESPACE:
        @_upstream_sio.on("booking_admin", namespace=BOOKING_NAMESPACE)
        def _on_booking_admin_ns(data):
            _handle_upstream_booking(data)
    else:
        @_upstream_sio.on("booking_admin")
        def _on_booking_admin(data):
            _handle_upstream_booking(data)

# -----------------------------------------------------------------------------
# Health check loop
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Public: start upstream bridge
# -----------------------------------------------------------------------------
#def start_upstream_bridge(app):
 #   global _started_upstream
  #  with _lock:
   #     if _started_upstream:
    #        return
     #   _started_upstream = True

    #_register_upstream_handlers()

    #def _runner():
     #   try:
      #      kwargs = {}
       #     if BOOKING_AUTH_TOKEN:
        #        kwargs["headers"] = {"Authorization": f"Bearer {BOOKING_AUTH_TOKEN}"}
         #   _upstream_sio.connect(BOOKING_SOCKET_URL, **kwargs)
          #  _upstream_sio.wait()
        #except Exception as e:
         #   _log_err("Upstream bridge connection error: %s", e)
         
    #def _runner():
     #   try:
      #     kwargs = {}
       #    if BOOKING_AUTH_TOKEN:
        #       kwargs["headers"] = {"Authorization": f"Bearer {BOOKING_AUTH_TOKEN}"}
        
        # Remove any 'timeout' parameter - use 'wait_timeout' if needed
         #      kwargs["wait_timeout"] = 20   # Optional: set connection timeout
        
          #     _upstream_sio.connect(BOOKING_SOCKET_URL, **kwargs)
           #    _upstream_sio.wait()
        #except Exception as e:
         #     _log_err("Upstream bridge connection error: %s", e)

    #t = threading.Thread(target=_runner, name="booking-upstream-bridge", daemon=True)
    #t.start()

    #hc = threading.Thread(target=_enhanced_health_check_loop, name="booking-upstream-health", daemon=True)
    #hc.start()
    
def start_upstream_bridge(app):
    global _started_upstream
    with _lock:
        if _started_upstream:
            return
        _started_upstream = True

    _register_upstream_handlers()

    def _runner():
        try:
            if not _connect_with_retry():
                _log_err("Failed to establish initial connection after maximum attempts")
            _upstream_sio.wait()
        except Exception as e:
            _log_err("Upstream bridge connection error: %s", e)

    def _health_check_wrapper():
        """Wrapper to run health check with Flask app context"""
        with app.app_context():
            _enhanced_health_check_loop_with_context(app)

    t = threading.Thread(target=_runner, name="booking-upstream-bridge", daemon=True)
    t.start()

    # Pass app to health check thread
    hc = threading.Thread(target=_health_check_wrapper, name="booking-upstream-health", daemon=True)
    hc.start()

def _enhanced_health_check_loop_with_context(app):
    """Enhanced health check with proper rate limiting"""
    backoff_delay = 30.0  # Start with 30 seconds (not 1 second)
    max_backoff = 300.0   # Max 5 minutes between attempts
    consecutive_failures = 0
    
    while True:
        try:
            now = time.time()
            
            if not _upstream_sio.connected:
                # Don't retry too fast - this prevents 429 errors
                if consecutive_failures > 0:
                    time.sleep(backoff_delay)
                
                app.logger.warning(
                    "Health check: upstream not connected (attempt %d), reconnecting...", 
                    consecutive_failures + 1
                )
                
                try:
                    if hasattr(_upstream_sio, 'disconnect'):
                        _upstream_sio.disconnect()
                    
                    kwargs = {}
                    if BOOKING_AUTH_TOKEN:
                        kwargs["headers"] = {"Authorization": f"Bearer {BOOKING_AUTH_TOKEN}"}
                    
                    _upstream_sio.connect(BOOKING_SOCKET_URL, **kwargs)
                    
                    # Reset backoff on success
                    backoff_delay = 30.0
                    consecutive_failures = 0
                    app.logger.info("Health check: reconnection successful")
                    
                except Exception as e:
                    consecutive_failures += 1
                    backoff_delay = min(backoff_delay * 1.5, max_backoff)  # Gentler exponential backoff
                    app.logger.error("Health check reconnect failed (attempt %d): %s", consecutive_failures, e)
            
            else:
                # Connection is healthy
                consecutive_failures = 0
                backoff_delay = 30.0
                
                # Check admin heartbeat (increased timeout)
                if now - _last_admin_heartbeat > 300:  # 5 minutes instead of 2
                    app.logger.warning("No admin heartbeat for 5+ minutes, rejoining admin...")
                    _join_upstream_admin()

            # Much longer sleep to avoid rate limiting
            time.sleep(60)  # Check every 60 seconds instead of 30
            
        except Exception as e:
            app.logger.exception("Health check loop crashed: %s", e)
            time.sleep(60)



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

            with _lock:
                is_new = int(vendor_id) not in _joined_vendor_ids
                if is_new:
                    _joined_vendor_ids.add(int(vendor_id))
            if is_new and _upstream_sio.connected:
                _join_upstream_vendor(int(vendor_id))
        except Exception as e:
            _log_err("dashboard_join_vendor error: %s", e)

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
            
