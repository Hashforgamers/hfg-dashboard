"""Server-authoritative kiosk windows, code redemption and offline expiry."""
from datetime import datetime, timedelta, timezone
from functools import wraps
import math
import threading

import pytz
from flask import current_app, g, jsonify, make_response, request
from sqlalchemy import text

from app.extension.extensions import db
from app.services.kiosk_security import (KioskError, check_scope, positive_id, rate_limit,
                                        runtime_identity, vendor_lock)

IST = pytz.timezone('Asia/Kolkata')


def utc_window(day, start, end):
    if day is None or start is None or end is None or start == end:
        raise KioskError('invalid_booking_window', 409)
    begin = IST.localize(datetime.combine(day, start)).astimezone(timezone.utc)
    finish = IST.localize(datetime.combine(day, end)).astimezone(timezone.utc)
    if finish < begin:
        finish += timedelta(days=1)
    return begin, finish


def assigned_consoles(row):
    details = row.get('squad_details') or {}
    ids = {int(cid) for cid in details.get('assigned_console_ids', [])}
    if row.get('console_id'):
        ids.add(int(row['console_id']))
    released = {int(cid) for cid in details.get('released_console_ids', [])}
    return ids - released


def booking_window(vendor_id, booking_id, console_id):
    vendor_id, booking_id, console_id = map(positive_id, (vendor_id, booking_id, console_id))
    table = f'VENDOR_{vendor_id}_DASHBOARD'
    anchor = db.session.execute(text(f'''
        SELECT d.*, b.squad_details, b.access_code_id, b.status AS booking_status,
               COALESCE(d.username, u.name) AS resolved_user_name, ag.game_name,
               v.cafe_name AS vendor_name
        FROM {table} d JOIN bookings b ON b.id = d.book_id
        JOIN available_games ag ON ag.id=b.game_id
        JOIN vendors v ON v.id=ag.vendor_id
        LEFT JOIN users u ON u.id=d.user_id
        WHERE d.book_id = :bid
    '''), {'bid': booking_id}).mappings().first()
    if not anchor:
        raise KioskError('booking_not_found', 404)
    # Released squad members may inspect their ended session, but cannot restart it.
    released_ids = {int(cid) for cid in (anchor.get('squad_details') or {}).get('released_console_ids', [])}
    if console_id not in assigned_consoles(anchor) and console_id not in released_ids and int(anchor.get('console_id') or 0) != console_id:
        raise KioskError('booking_console_mismatch', 403)
    begin, finish = utc_window(anchor['date'], anchor['start_time'], anchor['end_time'])
    rows = db.session.execute(text(f'''
        SELECT d.*, b.squad_details, b.access_code_id, b.status AS booking_status
        FROM {table} d JOIN bookings b ON b.id = d.book_id
        WHERE d.user_id = :uid AND d.game_id = :gid
          AND b.access_code_id IS NOT DISTINCT FROM :code_id
          AND d.book_status IN ('current', 'completed')
        ORDER BY d.date, d.start_time
    '''), {'uid': anchor['user_id'], 'gid': anchor['game_id'], 'code_id': anchor['access_code_id']}).mappings().all()
    group = [anchor]
    # Extend only a contiguous window actually assigned to this console.
    for row in rows:
        if int(row['book_id']) == booking_id or console_id not in assigned_consoles(row) or row['booking_status'] in ('cancelled', 'canceled'):
            continue
        row_start, row_end = utc_window(row['date'], row['start_time'], row['end_time'])
        if row_start == finish:
            finish = row_end
            group.append(row)
    now = datetime.now(timezone.utc)
    cancelled = anchor['book_status'] in ('cancelled', 'canceled') or anchor['booking_status'] in ('cancelled', 'canceled')
    live = console_id not in released_ids and any(r['book_status'] == 'current' for r in group)
    status = 'cancelled' if cancelled else ('active' if live and begin <= now < finish else 'expired')
    return {
        'booking_id': booking_id, 'booking_ids': [int(r['book_id']) for r in group],
        'console_id': console_id, 'vendor_id': vendor_id, 'game_id': int(anchor['game_id']),
        'user_id': int(anchor['user_id']) if anchor['user_id'] else None,
        'user_name': anchor.get('resolved_user_name'),
        'game_name': anchor.get('game_name'), 'vendor_name': anchor.get('vendor_name'),
        'start_time': begin.isoformat(), 'end_time': finish.isoformat(),
        'server_time': now.isoformat(), 'status': status,
        'seconds_remaining': max(0, math.ceil((finish - now).total_seconds())) if status == 'active' else 0,
    }


def secure_start(fn):
    @wraps(fn)
    def wrapped():
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            raise KioskError('invalid_json', 400)
        console_id = positive_id(data.get('console_id'))
        rate_limit(console_id)
        identity = runtime_identity()
        code = data.get('access_code') or data.get('accessCode')
        if identity['kind'] == 'kiosk' and not code:
            raise KioskError('access_code_required', 400)
        vendor_id = identity['vendor_id']
        check_scope(identity, vendor_id, console_id)
        vendor_lock(vendor_id)
        code_id = None
        redemption = None
        try:
            if code:
                if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdigit():
                    raise KioskError('invalid_access_code', 400)
                access = db.session.execute(text('''
                    SELECT id FROM access_booking_codes WHERE access_code=:code FOR UPDATE
                '''), {'code': code}).first()
                if not access:
                    raise KioskError('invalid_access_code', 404)
                code_id = access.id
                redemption = db.session.execute(text('SELECT console_id, booking_id FROM kiosk_code_redemptions WHERE access_code_id=:aid'),
                                                 {'aid': code_id}).first()
                if redemption and redemption.console_id != console_id:
                    raise KioskError('access_code_used', 409)
                target = db.session.execute(text(f'''
                    SELECT b.id, b.game_id, ag.vendor_id, d.book_status, d.console_id,
                           d.date, d.start_time, d.end_time, b.status, b.squad_details
                    FROM bookings b JOIN available_games ag ON ag.id=b.game_id
                    JOIN VENDOR_{vendor_id}_DASHBOARD d ON d.book_id=b.id
                    WHERE b.access_code_id=:aid AND ag.vendor_id=:vid
                      AND (:redeemed_bid IS NULL OR b.id=:redeemed_bid)
                    ORDER BY CASE WHEN d.book_status='current' THEN 0
                                  WHEN d.book_status='upcoming' THEN 1 ELSE 2 END, d.date, d.start_time
                    LIMIT 1
                '''), {'aid': code_id, 'vid': vendor_id, 'redeemed_bid': redemption.booking_id if redemption else None}).mappings().first()
            else:
                bid = positive_id(data.get('booking_id'))
                target = db.session.execute(text(f'''
                    SELECT b.id, b.game_id, ag.vendor_id, d.book_status, d.console_id,
                           d.date, d.start_time, d.end_time, b.status, b.squad_details
                    FROM bookings b JOIN available_games ag ON ag.id=b.game_id
                    JOIN VENDOR_{vendor_id}_DASHBOARD d ON d.book_id=b.id
                    WHERE b.id=:bid AND ag.vendor_id=:vid
                '''), {'bid': bid, 'vid': vendor_id}).mappings().first()
            if not target:
                raise KioskError('booking_not_found', 404)
            for field, expected in [('booking_id', target['id']), ('vendor_id', vendor_id), ('game_id', target['game_id'])]:
                if data.get(field) is not None and positive_id(data[field]) != int(expected):
                    raise KioskError('booking_scope_mismatch', 403)
                data[field] = int(expected)
            check_scope(identity, vendor_id, console_id, target['game_id'])
            additional = data.get('additional_console_ids') or []
            if not isinstance(additional, list):
                raise KioskError('invalid_console_ids', 400)
            for cid in additional:
                check_scope(identity, vendor_id, cid, target['game_id'])
            if redemption:
                window = booking_window(vendor_id, target['id'], console_id)
                if window['status'] != 'active':
                    raise KioskError('access_code_used', 409)
                db.session.rollback()
                return jsonify({'status': 'success', 'data': window}), 200
            if target['status'] in ('cancelled', 'canceled') or target['book_status'] not in ('upcoming', 'current'):
                raise KioskError('session_ended', 409)
            if target['console_id'] and int(target['console_id']) != console_id:
                raise KioskError('booking_console_mismatch', 403)
            if target['book_status'] == 'current':
                window = booking_window(vendor_id, target['id'], console_id)
                if window['status'] != 'active':
                    raise KioskError('session_ended', 409)
            else:
                begin, finish = utc_window(target['date'], target['start_time'], target['end_time'])
                if not begin <= datetime.now(timezone.utc) < finish:
                    raise KioskError('session_not_active', 409)
            if code_id:
                db.session.execute(text('''INSERT INTO kiosk_code_redemptions(access_code_id, console_id, booking_id)
                    VALUES (:aid,:cid,:bid) ON CONFLICT (access_code_id) DO NOTHING'''), {'aid': code_id, 'cid': console_id, 'bid': target['id']})
            g.kiosk_after_commit = []
            g.kiosk_transaction = True
            g.kiosk_access_code_id = code_id
            response = make_response(fn())
            if response.status_code >= 400:
                db.session.rollback()
                return response
            db.session.flush()
            window = booking_window(vendor_id, target['id'], console_id)
            if window['status'] != 'active':
                raise KioskError('session_not_active', 409)
            db.session.commit()
            g.kiosk_transaction = False
            from app.routes import _invalidate_vendor_caches
            from app.services.websocket_service import _emit_to_kiosk
            _invalidate_vendor_caches(vendor_id)
            _emit_to_kiosk(console_id, 'unlock_request', dict(window, type='unlock_request'))
            for publish in g.kiosk_after_commit:
                try:
                    publish()
                except Exception:
                    current_app.logger.exception('Committed kiosk session notification failed')
            # Notification reads must not leave an aborted/read transaction open.
            db.session.rollback()
            return jsonify({'status': 'success', 'data': window}), 200
        except Exception:
            db.session.rollback()
            raise
    return wrapped


def expire_vendor(vendor_id):
    """Finalize elapsed/cancelled rows even with no connected kiosk."""
    vendor_id = positive_id(vendor_id)
    vendor_lock(vendor_id)
    table = f'VENDOR_{vendor_id}_DASHBOARD'
    rows = db.session.execute(text(f'''
        SELECT d.book_id, d.console_id, d.date, d.start_time, d.end_time,
               b.squad_details, b.status AS booking_status
        FROM {table} d JOIN bookings b ON b.id=d.book_id
        WHERE d.book_status='current' FOR UPDATE OF d, b
    ''')).mappings().all()
    now = datetime.now(timezone.utc)
    expired, candidates, occupied = [], set(), set()
    for row in rows:
        try:
            _, finish = utc_window(row['date'], row['start_time'], row['end_time'])
        except KioskError:
            finish = now  # Fail closed for corrupt schedules; do not block other sessions.
        if finish <= now or row['booking_status'] in ('cancelled', 'canceled'):
            expired.append(row['book_id'])
            candidates.update(assigned_consoles(row))
        else:
            occupied.update(assigned_consoles(row))
    if expired:
        db.session.execute(text(f'''UPDATE {table} SET book_status = CASE
            WHEN book_id IN (SELECT id FROM bookings WHERE status IN ('cancelled','canceled'))
            THEN 'cancelled' ELSE 'completed' END WHERE book_id=ANY(:ids)'''), {'ids': expired})
        db.session.execute(text("UPDATE bookings SET status='completed' WHERE id=ANY(:ids) AND status NOT IN ('cancelled','canceled')"), {'ids': expired})
        for cid in candidates - occupied:
            db.session.execute(text(f'UPDATE VENDOR_{vendor_id}_CONSOLE_AVAILABILITY SET is_available=TRUE WHERE console_id=:cid'), {'cid': cid})
    db.session.commit()
    if expired:
        from app.routes import _invalidate_vendor_caches
        from app.services.websocket_service import socketio, _emit_to_kiosk
        _invalidate_vendor_caches(vendor_id)
        for cid in candidates - occupied:
            _emit_to_kiosk(cid, 'session_expired', {'console_id': cid})
            socketio.emit('console_availability', {'vendorId': vendor_id, 'console_id': cid, 'is_available': True}, room=f'vendor_{vendor_id}')
    return len(expired)


def sweep_expired():
    # Discover only tables actually present; not every vendor has been provisioned.
    import re
    names = db.session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname=current_schema() AND tablename LIKE 'vendor_%_dashboard'")).scalars().all()
    count = 0
    for name in names:
        match = re.fullmatch(r'vendor_(\d+)_dashboard', name)
        if not match:
            continue
        try:
            count += expire_vendor(int(match[1]))
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Kiosk expiry failed vendor=%s', match[1])
    return count


def start_expiry_worker(app):
    # Each web worker may sweep; per-vendor DB locks serialize across processes.
    # Restart performs an immediate catch-up, then sweeps every 30 seconds.
    if app.config.get('TESTING') or not app.config.get('KIOSK_EXPIRY_ENABLED', True):
        return
    def run():
        while True:
            with app.app_context():
                try:
                    sweep_expired()
                except Exception:
                    db.session.rollback()
                    app.logger.exception('Kiosk expiry sweep failed')
                finally:
                    db.session.remove()
            threading.Event().wait(30)
    threading.Thread(target=run, name='kiosk-expiry', daemon=True).start()
