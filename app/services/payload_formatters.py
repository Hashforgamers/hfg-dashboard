# app/services/payload_formatters.py
from typing import Any, Dict, Optional
import hashlib

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
    raw = f"{row.get('book_id')}|{date_val}|{start_time}|{end_time}"
    session_identifier = f"sess-{row.get('book_id')}-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:10]}"

    console_name = row.get("console_name")
    if console_name is not None:
        console_name = str(console_name).strip() or None

    return {
        "slotId": row["slot_id"],
        "bookId": row["book_id"],
        "startTime": _to_time_str(start_time),
        "endTime": _to_time_str(end_time),
        "status": "Booked" if row.get("status") != "pending_verified" else "Available",
        "consoleType": console_name or (f"HASH{row['console_id']}" if row.get("console_id") is not None else None),
        "consoleNumber": str(row.get("console_number") or row["console_id"]) if row.get("console_id") is not None else None,
        "consoleCode": row.get("console_number"),
        "consoleId": row.get("console_id"),
        "username": row.get("username"),
        "userId": row.get("user_id"),
        "game_id": row.get("game_id"),
        "date": _to_date_str(date_val),  # ensure string
        "slot_price": row.get("single_slot_price"),
        "lifecycleStatus": "current",
        "lifecycleStep": 2,
        "sessionIdentifier": session_identifier,
        "squadEnabled": bool(row.get("squad_enabled", False)),
        "squadPlayerCount": int(row.get("squad_player_count", 1) or 1),
        "squadMembers": row.get("squad_members", []) or [],
        "squadDetails": row.get("squad_details", {}) or {},
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
            "squadDetails": data.get("squad_details") or data.get("squadDetails") or {},
            "squadEnabled": bool((data.get("squad_details") or data.get("squadDetails") or {}).get("enabled", False)),
            "squadPlayerCount": int((data.get("squad_details") or data.get("squadDetails") or {}).get("player_count", 1) or 1),
        }
        # Ensure core IDs exist
        if not payload["bookingId"] or not payload["slotId"]:
            return None
        return payload
    except Exception:
        return None
