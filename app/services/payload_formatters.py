# app/services/payload_formatters.py
from typing import Any, Dict, Optional

def _to_time_str(val: Any) -> str:
    try:
        return val.strftime("%I:%M %p")
    except Exception:
        return str(val) if val is not None else ""

def _to_date_str(val: Any) -> str:
    try:
        # date or datetime -> YYYY-MM-DD
        return val.date().isoformat() if hasattr(val, "date") else val.isoformat()
    except Exception:
        return str(val) if val is not None else ""

def format_current_slot_item(*, row: Dict[str, Any]) -> Dict[str, Any]:
    start_time = row["start_time"]
    end_time = row["end_time"]
    date_val = row.get("date")

    return {
        "slotId": row["slot_id"],
        "bookId": row["book_id"],
        "startTime": _to_time_str(start_time),
        "endTime": _to_time_str(end_time),
        "status": "Booked" if row.get("status") != "pending_verified" else "Available",
        "consoleType": f"HASH{row['console_id']}" if row.get("console_id") is not None else None,
        "consoleNumber": str(row["console_id"]) if row.get("console_id") is not None else None,
        "username": row.get("username"),
        "userId": row.get("user_id"),
        "game_id": row.get("game_id"),
        "date": _to_date_str(date_val),  # ensure string
        "slot_price": row.get("single_slot_price"),
    }


def format_upcoming_booking_from_upstream(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convert upstream booking payload into the upcomingBookings item shape,
    but ONLY if status == 'confirmed' AND booking_status == 'upcoming'.
    """
    status_val = (data.get("status") or "").lower()
    booking_status_val = (data.get("booking_status") or data.get("book_status") or "").lower()

    if status_val != "confirmed":
        return None
    if booking_status_val != "upcoming":
        return None

    time_block = data.get("time") or data.get("processed_time")
    console_type = data.get("consoleType")
    console_number = data.get("consoleNumber")
    console_fragment = console_type if (console_type and console_number) else console_type or None

    status_label = data.get("statusLabel") or "Confirmed"

    try:
        payload = {
            "slotId": data.get("slotId") or data.get("slot_id"),
            "bookingId": data.get("bookingId") or data.get("booking_id"),
            "username": data.get("username"),
            "userId": data.get("userId") or data.get("user_id"),
            "game": data.get("game"),
            "consoleType": console_fragment,   # e.g., "Console-3"
            "time": time_block,                # "07:00 PM - 08:00 PM"
            "status": status_label,            # "Confirmed"
            "game_id": data.get("game_id"),
            "date": data.get("date"),
            "slot_price": data.get("slot_price"),
        }
        # Ensure core IDs exist
        if not payload["bookingId"] or not payload["slotId"]:
            return None
        return payload
    except Exception:
        return None
