"""Existing paid bookings use the same PC QR and acknowledgement as wallet play."""
from datetime import datetime, timedelta, timezone, date, time
from zoneinfo import ZoneInfo
import math
import secrets
import uuid
from sqlalchemy import text, bindparam
from app.extension.extensions import db
from app.models.cafe_wallet import CafePlaySession, CafeBookingClaim
from app.services.cafe_wallet_service import CafeError, audit, fingerprint, integer, key, policy, wallet

IST = ZoneInfo('Asia/Kolkata')
PAID = {'completed', 'done', 'settled', 'paid'}


def utc_window(row):
    day = row['date'] if isinstance(row['date'], date) else date.fromisoformat(row['date'])
    start = row['start_time'] if isinstance(row['start_time'], time) else time.fromisoformat(row['start_time'])
    end = row['end_time'] if isinstance(row['end_time'], time) else time.fromisoformat(row['end_time'])
    begin = datetime.combine(day, start, IST)
    finish = datetime.combine(day, end, IST)
    if finish == begin:
        raise CafeError('Invalid booking time. Please visit the desk.', 409)
    if finish < begin:
        finish += timedelta(days=1)
    return begin.astimezone(timezone.utc).replace(tzinfo=None), finish.astimezone(timezone.utc).replace(tzinfo=None)


def _rows(vendor_id, user_id, *, lock=False, ids=None):
    today = datetime.now(IST).date()
    conditions = 'AND d.date BETWEEN :first_day AND :last_day' if ids is None else 'AND b.id IN :ids'
    query = text(f'''SELECT b.id, b.user_id, b.game_id, b.status, b.squad_details,
            b.access_code_id, ag.game_name, d.date, d.start_time, d.end_time,
            d.book_status, d.console_id
        FROM bookings b JOIN available_games ag ON ag.id=b.game_id
        JOIN VENDOR_{int(vendor_id)}_DASHBOARD d ON d.book_id=b.id
        WHERE b.user_id=:uid AND ag.vendor_id=:vid {conditions}
        ORDER BY d.date, d.start_time, b.id
        {'FOR UPDATE OF b,d' if lock and db.engine.dialect.name == 'postgresql' else ''}''')
    params = {'uid': user_id, 'vid': vendor_id, 'first_day': today-timedelta(days=1), 'last_day': today+timedelta(days=1)}
    if ids is not None:
        query = query.bindparams(bindparam('ids', expanding=True)); params['ids'] = ids
    return [dict(r) for r in db.session.execute(query, params).mappings()]


def _payment_verified(rows, vendor_id, user_id, *, lock=False):
    ids = [r['id'] for r in rows]
    query = text('''SELECT booking_id, booking_type, amount, settlement_status
        FROM transactions WHERE booking_id IN :ids AND vendor_id=:vid AND user_id=:uid
        ''' + ('FOR UPDATE' if lock and db.engine.dialect.name == 'postgresql' else '')).bindparams(bindparam('ids', expanding=True))
    payments = db.session.execute(query, {'ids': ids, 'vid': vendor_id, 'uid': user_id}).mappings().all()
    by_booking = {bid: [] for bid in ids}
    for payment in payments:
        if payment['booking_type'] != 'additional_meals':
            by_booking[payment['booking_id']].append(payment)
    return all(items and all(str(p['settlement_status'] or '').lower() in PAID
                              and p['amount'] >= 0 for p in items) for items in by_booking.values())


def _reason(rows, link, *, lock=False):
    now = datetime.utcnow()
    if any(r['status'] != 'confirmed' or r['book_status'] != 'upcoming' for r in rows):
        return 'This booking has already started, ended or been cancelled.'
    for row in rows:
        details = row['squad_details'] or {}
        if isinstance(details, str):
            import json
            details = json.loads(details)
        if int(details.get('player_count') or 1) > 1:
            return 'Please ask the desk to assign PCs for your group booking.'
        if row['console_id'] and row['console_id'] != link.console_id:
            return 'This booking is assigned to another PC. Scan that PC’s QR.'
        compatible = db.session.execute(text('SELECT 1 FROM available_game_console WHERE available_game_id=:gid AND console_id=:cid'), {'gid': row['game_id'], 'cid': link.console_id}).first()
        if not compatible:
            return 'This booking requires a different type of PC or console.'
    begin, _ = utc_window(rows[0])
    _, finish = utc_window(rows[-1])
    if now < begin:
        return 'Your booked time has not started yet.'
    if now >= finish:
        return 'Your booked time has ended.'
    if not _payment_verified(rows, link.vendor_id, rows[0]['user_id'], lock=lock):
        return 'Please confirm the booking payment at the desk.'
    return None


def _groups(rows):
    groups = []
    for row in rows:
        # Only combine contiguous slots purchased together; unrelated bookings stay separate.
        previous = groups[-1][-1] if groups else None
        if (previous and row['access_code_id'] is not None
                and row['access_code_id'] == previous['access_code_id']
                and row['game_id'] == previous['game_id']
                and row['status'] == previous['status'] and row['book_status'] == previous['book_status']
                and utc_window(previous)[1] == utc_window(row)[0]):
            groups[-1].append(row)
        else:
            groups.append([row])
    return groups


def existing_bookings(link, user_id):
    rows = [r for r in _rows(link.vendor_id, user_id) if r['book_status'] in ('upcoming', 'current')
            and r['status'] not in ('cancelled', 'canceled', 'completed')]
    result = []
    for group in _groups(rows):
        begin, _ = utc_window(group[0]); _, finish = utc_window(group[-1])
        if finish <= datetime.utcnow():
            continue
        reason = _reason(group, link)
        claim = CafeBookingClaim.query.filter(CafeBookingClaim.booking_id.in_([r['id'] for r in group])).first()
        if claim:
            reason = 'This booking already has a PC session.'
        result.append({'booking_id': group[0]['id'], 'booking_ids': [r['id'] for r in group],
            'game_name': group[0]['game_name'], 'starts_at': begin.isoformat()+'Z', 'ends_at': finish.isoformat()+'Z',
            'can_start': reason is None, 'reason': reason, 'payment_required': False})
    return result


def reserve_booking(link, user_id, booking_id, idem):
    integer(booking_id); key(idem)
    fp = fingerprint(['existing_booking', link.console_id, booking_id])
    wallet(link.vendor_id, user_id)  # Same cafe lock as wallet starts; no money is changed.
    existing = CafePlaySession.query.filter_by(vendor_id=link.vendor_id, user_id=user_id, idempotency_key=idem).first()
    if existing:
        if existing.fingerprint != fp:
            raise CafeError('Idempotency key already used for another checkout', 409)
        return existing
    if not policy(link.vendor_id)['self_service']:
        raise CafeError('Self-service is disabled at this cafe', 403)
    from app.models.console import Console
    from app.models.console_link_session import ConsoleLinkSession
    console = Console.query.filter_by(id=link.console_id, vendor_id=link.vendor_id).populate_existing().with_for_update().first()
    link = ConsoleLinkSession.query.filter_by(id=link.id).populate_existing().with_for_update().first()
    if not console or not link or link.status != 'active':
        raise CafeError('PC is not linked', 409)
    if CafePlaySession.query.filter_by(console_claim=console.id).first():
        raise CafeError('PC is already reserved or playing', 409)
    rows = _rows(link.vendor_id, user_id, lock=True)
    group = next((g for g in _groups(rows) if g[0]['id'] == booking_id), None)
    if not group:
        raise CafeError('Booking not found for this gamer and cafe', 404)
    reason = _reason(group, link, lock=True)
    if reason:
        raise CafeError(reason, 409)
    ids = [r['id'] for r in group]
    if CafeBookingClaim.query.filter(CafeBookingClaim.booking_id.in_(ids)).first():
        raise CafeError('Booking already has a PC session', 409)
    available = db.session.execute(text(f'SELECT is_available FROM VENDOR_{int(link.vendor_id)}_CONSOLE_AVAILABILITY WHERE console_id=:cid'
        + (' FOR UPDATE' if db.engine.dialect.name == 'postgresql' else '')), {'cid': console.id}).all()
    if not available or not all(r[0] for r in available):
        raise CafeError('PC is unavailable', 409)
    _, finish = utc_window(group[-1])
    now = datetime.utcnow()
    session = CafePlaySession(id=str(uuid.uuid4()), vendor_id=link.vendor_id, user_id=user_id,
        console_id=console.id, link_id=link.id, console_claim=console.id, kind='existing_booking',
        booking_ids=ids, booking_end=finish, amount=0, minutes=math.ceil((finish-now).total_seconds()/60),
        idempotency_key=idem, fingerprint=fp, command_token=secrets.token_urlsafe(32), state='reserved',
        deadline=min(finish, now+timedelta(seconds=45)))
    db.session.add(session)
    for bid in ids:
        db.session.add(CafeBookingClaim(booking_id=bid, session_id=session.id))
    db.session.flush()
    db.session.execute(text(f'UPDATE VENDOR_{int(link.vendor_id)}_CONSOLE_AVAILABILITY SET is_available=false WHERE console_id=:cid'), {'cid': console.id})
    audit(link.vendor_id, {'id':f'gamer-{user_id}', 'name':'Gamer self-service'},
          'booking.start_requested', {'session_id':session.id, 'booking_ids':ids, 'console_id':console.id})
    return session


def acknowledge_booking(session, link, success):
    """Called with the cafe/session locks held; no commit or wallet ledger writes."""
    now = datetime.utcnow()
    rows = _rows(session.vendor_id, session.user_id, lock=True, ids=session.booking_ids)
    reason = None
    if success and now < session.deadline:
        if len(rows) != len(session.booking_ids):
            reason = 'Booking no longer exists.'
        else:
            reason = _reason(rows, link, lock=True)
            if utc_window(rows[-1])[1] != session.booking_end:
                reason = 'Booking schedule changed. Scan again.'
    if not success or now >= session.deadline or reason:
        session.state = 'failed'
        CafeBookingClaim.query.filter_by(session_id=session.id).delete(synchronize_session=False)
        from app.services.cafe_wallet_service import release_console
        release_console(session)
        action = 'booking.start_failed'
    else:
        session.state = 'active'; session.started_at = now; session.ends_at = session.booking_end
        db.session.flush()  # Database guard allows only this active booking/PC combination.
        update = text(f"UPDATE VENDOR_{int(session.vendor_id)}_DASHBOARD SET book_status='current', console_id=:cid WHERE book_id IN :ids").bindparams(bindparam('ids', expanding=True))
        db.session.execute(update, {'cid':session.console_id, 'ids':session.booking_ids})
        update = text("UPDATE bookings SET status='checked_in' WHERE id IN :ids").bindparams(bindparam('ids', expanding=True))
        db.session.execute(update, {'ids':session.booking_ids})
        action = 'booking.started'
    audit(session.vendor_id, {'id':f'pc-{link.console_id}', 'name':f'PC {link.console_id}'}, action,
          {'session_id':session.id, 'booking_ids':session.booking_ids, 'reason':reason})
    return session


def reconcile_booking(session):
    """Keep the new and legacy views aligned, including cancellation during play."""
    rows = _rows(session.vendor_id, session.user_id, lock=True, ids=session.booking_ids)
    cancelled = (len(rows) != len(session.booking_ids)
        or any(r['status'] in ('cancelled','canceled') or r['book_status'] in ('cancelled','canceled') for r in rows)
        or not _payment_verified(rows, session.vendor_id, session.user_id, lock=True))
    elapsed = session.ends_at <= datetime.utcnow()
    if not cancelled and not elapsed:
        return False
    session.state = 'cancelled' if cancelled else 'completed'
    update = text(f"UPDATE VENDOR_{int(session.vendor_id)}_DASHBOARD SET book_status=:state WHERE book_id IN :ids AND book_status='current'").bindparams(bindparam('ids', expanding=True))
    db.session.execute(update, {'state':session.state,'ids':session.booking_ids})
    update = text("UPDATE bookings SET status='completed' WHERE id IN :ids AND status='checked_in'").bindparams(bindparam('ids', expanding=True))
    db.session.execute(update, {'ids':session.booking_ids})
    audit(session.vendor_id, {'id':'system','name':'Session reconciler'}, 'booking.'+session.state,
          {'session_id':session.id,'booking_ids':session.booking_ids})
    return True
