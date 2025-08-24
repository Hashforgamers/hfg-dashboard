# app/services/payload_formatters.py
from typing import Any, Dict, Optional

def format_upcoming_booking_from_upstream(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convert upstream booking event payload into the upcomingBookings item shape
    used by GET /getLandingPage/vendor/<vendor_id>.

    Expected upstream canonical keys (per your emitter):
      bookingId, slotId, vendorId, userId, username, game, game_id, date,
      slot_price, status, booking_status, time (e.g., "09:00 AM - 10:00 AM")
    """
    # Only emit if upstream marks this booking as 'upcoming'
    if (data.get("booking_status") or data.get("book_status")) != "upcoming":
        return None

    # Time block from upstream is a string like "09:00 AM - 10:00 AM"
    time_block = data.get("time") or data.get("processed_time")

    # Console fields are optional; keep them if present
    console_type = data.get("consoleType")
    console_number = data.get("consoleNumber")
    console_fragment = None
    if console_type and console_number:
        # Keep the same style as the initial API (“Console-<id>” is already set upstream)
        console_fragment = console_type

    # Status label for UI
    status_label = data.get("statusLabel") or ("Confirmed" if data.get("status") != "pending_verified" else "Pending")

    try:
        payload = {
            "slotId": data.get("slotId") or data.get("slot_id"),
            "bookingId": data.get("bookingId") or data.get("booking_id"),
            "username": data.get("username"),
            "userId": data.get("userId") or data.get("user_id"),
            "game": data.get("game"),
            "consoleType": console_fragment,  # ex: "Console-3"
            "time": time_block,               # ex: "09:00 AM - 10:00 AM"
            "status": status_label,           # "Confirmed" or "Pending"
            "game_id": data.get("game_id"),
            "date": data.get("date"),         # "YYYY-MM-DD"
            "slot_price": data.get("slot_price"),
        }
        # Ensure minimal required keys exist
        if not payload["bookingId"] or not payload["slotId"]:
            return None
        return payload
    except Exception:
        return None
