"""QR wallet starts consume the same dated capacity as app and desk bookings."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import text
from app.extension.extensions import db
from app.models.cafe_wallet import CafeSlotReservation
from app.services.pricing_math import slot_window
from app.services.slot_capacity import reserve_slot, release_slot

IST = ZoneInfo('Asia/Kolkata')


def _day(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def _time(value):
    return time.fromisoformat(value) if isinstance(value, str) else value


def covered_slots(rows, start, end):
    windows = []
    seen = set()
    for row in rows:
        key = (_day(row['date']), row['slot_id'])
        if key in seen:
            raise ValueError('Duplicate dated slot rows; update the console schedule')
        seen.add(key)
        left, right = slot_window(key[0], _time(row['start_time']), _time(row['end_time']))
        if left < end and start < right:
            windows.append((max(left,start), min(right,end), row))
    windows.sort(key=lambda item: (item[0],item[1]))
    cursor = start
    result = []
    for left, right, row in windows:
        if left != cursor:
            raise ValueError('Console slots overlap or do not cover this session; update the console schedule')
        result.append(row)
        cursor = right
    if cursor != end:
        raise ValueError('Console schedule does not cover this session')
    return result


def scheduled_slots(link, start, end, *, lock=False):
    overlap_filter = '''AND v.date+s.start_time < :window_end
          AND :window_start < v.date+s.end_time + CASE WHEN s.end_time<=s.start_time
              THEN interval '1 day' ELSE interval '0 day' END''' if db.engine.dialect.name == 'postgresql' else ''
    query = text(f'''SELECT v.date,v.slot_id,v.available_slot,v.is_available,s.start_time,s.end_time
        FROM VENDOR_{int(link.vendor_id)}_SLOT v JOIN slots s ON s.id=v.slot_id
        JOIN available_games ag ON ag.id=s.gaming_type_id
        JOIN available_game_console ac ON ac.available_game_id=ag.id
        WHERE v.vendor_id=:vendor AND ag.vendor_id=:vendor AND ac.console_id=:console
          AND v.date BETWEEN :first AND :last
          {overlap_filter}
        ORDER BY v.date,v.slot_id
        {'FOR UPDATE OF v' if lock and db.engine.dialect.name == 'postgresql' else ''}''')
    rows = db.session.execute(query, {'vendor':link.vendor_id, 'console':link.console_id,
        'first':start.date()-timedelta(days=1), 'last':end.date(),
        'window_start':start, 'window_end':end}).mappings().all()
    return covered_slots(rows, start, end)


def ensure_console_window(link, start, end, *, exclude_bookings=()):
    # The console lock and database assignment guard serialize writes; do not
    # take dashboard row locks in the opposite order to legacy assignments.
    rows = db.session.execute(text(f'''SELECT book_id,date,start_time,end_time
        FROM VENDOR_{int(link.vendor_id)}_DASHBOARD
        WHERE console_id=:console AND book_status IN ('upcoming','current')
          AND date BETWEEN :first AND :last'''),
        {'console':link.console_id, 'first':start.date()-timedelta(days=1), 'last':end.date()}).mappings().all()
    for row in rows:
        if row['book_id'] in exclude_bookings:
            continue
        left,right = slot_window(_day(row['date']),_time(row['start_time']),_time(row['end_time']))
        if left < end and start < right:
            raise ValueError('This PC has another booking during the selected session')


def hold_slots(session, rows):
    for row in rows:
        reserve_slot(db.session,session.vendor_id,row['slot_id'],_day(row['date']))
        db.session.add(CafeSlotReservation(session_id=session.id,vendor_id=session.vendor_id,
            slot_id=row['slot_id'],date=_day(row['date']),units=1))


def release_slots(session):
    # Session state is locked by the caller. Released claims persist for audit
    # and make repeated acknowledgements/expiry runs a no-op.
    claims = CafeSlotReservation.query.filter_by(session_id=session.id,released_at=None).order_by(
        CafeSlotReservation.date,CafeSlotReservation.slot_id).with_for_update().all()
    for claim in claims:
        release_slot(db.session,claim.vendor_id,claim.slot_id,claim.date,claim.units)
        claim.released_at = datetime.utcnow()


def local_window(begin, end):
    return (begin.replace(tzinfo=timezone.utc).astimezone(IST).replace(tzinfo=None),
            end.replace(tzinfo=timezone.utc).astimezone(IST).replace(tzinfo=None))


def notify_slot_changes(session):
    """Publish invalidation only after the caller has committed the mutation."""
    from flask import current_app
    try:
        from app.services.websocket_service import socketio
        payload = {'vendor_id':session.vendor_id, 'console_id':session.console_id,
                   'session_id':session.id, 'state':session.state}
        from app.services.cafe_continuation_service import publish_session
        publish_session(session)
        room = f'vendor_{session.vendor_id}'
        socketio.emit('booking_slots_updated',payload,room=room)
        available = db.session.execute(text(f'SELECT is_available FROM VENDOR_{int(session.vendor_id)}_CONSOLE_AVAILABILITY WHERE console_id=:console'),
            {'console':session.console_id}).scalar()
        if available is not None:
            socketio.emit('console_availability',dict(payload,is_available=bool(available)),room=room)
    except Exception:
        current_app.logger.exception('Could not notify QR slot change session=%s',session.id)


def extend_overtime_slots(session, now):
    """Hold newly occupied dated slots while ongoing play runs beyond funded time."""
    from types import SimpleNamespace
    from datetime import timedelta
    link=SimpleNamespace(vendor_id=session.vendor_id,console_id=session.console_id)
    start,end=local_window(session.ends_at,now+timedelta(seconds=45))
    rows=scheduled_slots(link,start,end,lock=True)
    held={(r.date,r.slot_id) for r in CafeSlotReservation.query.filter_by(session_id=session.id,released_at=None).all()}
    for row in rows:
        if (_day(row['date']),row['slot_id']) in held:
            continue
        if row['available_slot']<1:
            from flask import current_app
            current_app.logger.warning('Overtime capacity conflict vendor=%s console=%s slot=%s',session.vendor_id,session.console_id,row['slot_id'])
            continue
        hold_slots(session,[row])
    notify_slot_changes(session)
