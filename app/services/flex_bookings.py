"""Read/release side of flex-start bookings created by hfg-booking.

A flex booking keeps slot_id/booked date on its base slot and holds every other
dated slot its window overlaps in cafe_slot_reservations under
``flex:<booking_id>``. Its exact window is stored on the dashboard row (so
kiosk, overview and console guards already use it) and on bookings.start_at /
end_at / timing_mode (20261126_flex_start_bookings.sql). Everything here is a
no-op for slot bookings and before that migration.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.extension.extensions import db

IST = ZoneInfo('Asia/Kolkata')
_columns_ready = False


def hold_key(booking_id):
    return f'flex:{int(booking_id)}'


def hold_keys(booking_ids):
    return [hold_key(b) for b in booking_ids or [] if str(b).lstrip('-').isdigit() and int(b) > 0]


def _ready():
    global _columns_ready
    if _columns_ready:
        return True
    if db.engine.dialect.name != 'postgresql':
        return False
    count = db.session.execute(text("""SELECT count(*) FROM information_schema.columns
        WHERE table_schema=current_schema() AND table_name='bookings'
          AND column_name IN ('start_at','end_at','duration_minutes','timing_mode')""")).scalar()
    _columns_ready = int(count or 0) == 4
    return _columns_ready


def flex_windows(booking_ids):
    """{booking_id: {timingMode, startAt, endAt, durationMinutes}} for flex bookings only."""
    ids = sorted({int(b) for b in booking_ids or [] if b is not None})
    if not ids or not _ready():
        return {}
    rows = db.session.execute(text("""SELECT id,start_at,end_at,duration_minutes FROM bookings
        WHERE id=ANY(:ids) AND timing_mode='flex'"""), {'ids': ids}).mappings()
    result = {}
    for row in rows:
        start = row['start_at'].astimezone(IST).isoformat() if row['start_at'] else None
        end = row['end_at'].astimezone(IST).isoformat() if row['end_at'] else None
        result[int(row['id'])] = {'timingMode': 'flex', 'timing_mode': 'flex', 'startAt': start, 'start_at': start,
                                  'endAt': end, 'end_at': end, 'durationMinutes': row['duration_minutes']}
    return result


def release_flex_holds(vendor_id, booking_id):
    """Give back a flex booking's extra slot units once (released claims stay for audit)."""
    from app.models.cafe_wallet import CafeSlotReservation
    from app.services.slot_capacity import release_slot
    claims = CafeSlotReservation.query.filter_by(session_id=hold_key(booking_id), vendor_id=int(vendor_id),
                                                 released_at=None).order_by(
        CafeSlotReservation.date, CafeSlotReservation.slot_id).with_for_update().all()
    for claim in claims:
        release_slot(db.session, claim.vendor_id, claim.slot_id, claim.date, claim.units)
        claim.released_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return len(claims)
