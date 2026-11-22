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
    ids = {int(cid) for cid in details.get('assigned_console_ids', []) if int(cid)>0}
    # Legacy onboarding/booking rows use -1 (and sometimes 0) for unassigned.
    if row.get('console_id') and int(row['console_id'])>0:
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
          AND d.book_status IN ('current', 'completed')
        ORDER BY d.date, d.start_time
    '''), {'uid': anchor['user_id'], 'gid': anchor['game_id']}).mappings().all()
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
    status = 'cancelled' if cancelled else ('active' if live and begin <= now else 'expired')
    result = {
        'booking_id': booking_id, 'booking_ids': [int(r['book_id']) for r in group],
        'console_id': console_id, 'vendor_id': vendor_id, 'game_id': int(anchor['game_id']),
        'user_id': int(anchor['user_id']) if anchor['user_id'] else None,
        'user_name': anchor.get('resolved_user_name'),
        'game_name': anchor.get('game_name'), 'vendor_name': anchor.get('vendor_name'),
        'start_time': begin.isoformat(), 'end_time': finish.isoformat(),
        'server_time': now.isoformat(), 'status': status,
        'seconds_remaining': max(0, math.ceil((finish - now).total_seconds())) if status == 'active' else 0,
        'auto_lock_at_end': False, 'stop_at': None,
        'overtime_seconds': max(0, math.ceil((now-finish).total_seconds())) if status == 'active' else 0,
    }

    has_extensions=bool(db.session.execute(text("SELECT to_regclass('kiosk_runtime_sessions')")).scalar()) if db.engine.dialect.name=='postgresql' else False
    if has_extensions:
        from app.services.session_extensions import RuntimeSession, snapshot
        managed=RuntimeSession.query.filter_by(vendor_id=vendor_id,console_id=console_id,source_kind='booking',source_id=str(booking_id)).first()
        if managed:
            state=snapshot(managed)
            result.update(runtime=state,end_time=state['reserved_until'],stop_at=state['stop_at'],
                auto_lock_at_end=False,play_allowed=state['play_allowed'],status='active' if state['play_allowed'] else 'expired')
            result['seconds_remaining']=max(0,int((managed.reserved_until-datetime.utcnow()).total_seconds())) if state['play_allowed'] else 0
    from app.services.pc_commands import delivery
    result['delivery']=delivery(vendor_id,console_id,booking_id)
    result['session_ref']={'kind':'booking','id':str(booking_id)}
    return result


def notify_console_runtime(vendor_id, console_ids, ended_booking_id=None, unlock_only=False):
    """Publish committed dashboard state to each linked PC, including squad PCs.

    unlock_only: for bookings started by another service; never send a lock."""
    from app.services.websocket_service import _emit_to_kiosk
    try:
        rows = db.session.execute(text(f"""
            SELECT d.*, b.squad_details FROM VENDOR_{positive_id(vendor_id)}_DASHBOARD d
            JOIN bookings b ON b.id=d.book_id
            WHERE d.book_status='current'
              AND b.status NOT IN ('cancelled','canceled')
            ORDER BY d.date,d.start_time,d.book_id
        """)).mappings().all()
        for cid in sorted({positive_id(cid) for cid in console_ids}):
            active = None
            for row in rows:
                if cid not in assigned_consoles(row):
                    continue
                window = booking_window(vendor_id, row['book_id'], cid)
                if window['status'] == 'active':
                    active = window
                    break
            if active:
                from app.services.session_extensions import ready,attach
                if ready():
                    from app.models.console_link_session import ConsoleLinkSession
                    link=ConsoleLinkSession.query.filter_by(vendor_id=vendor_id,console_id=cid,status='active').first()
                    if link:
                        attach(link,{'kind':'booking','id':str(active['booking_id'])})
                        active=booking_window(vendor_id,active['booking_id'],cid)
                from app.services.pc_commands import issue
                active['delivery']=issue(vendor_id,cid,active['booking_id']) or {'state':'unconfirmed','acknowledged':False}
                db.session.commit()
                _emit_to_kiosk(cid, 'unlock_request', dict(active, type='unlock_request'))
            elif unlock_only:
                continue
            else:
                # A booking release/reconnect must never lock another QR gamer.
                if db.session.execute(text("SELECT to_regclass('cafe_play_sessions')")).scalar():
                    if db.session.execute(text("SELECT 1 FROM cafe_play_sessions WHERE vendor_id=:vid AND console_id=:cid AND state IN ('reserved','active') LIMIT 1"),{'vid':vendor_id,'cid':cid}).scalar():
                        continue
                payload={
                    'console_id': cid, 'vendor_id': int(vendor_id),
                    'reason': 'dashboard_session_ended',
                }
                if ended_booking_id:
                    from app.services.pc_commands import issue
                    payload['session_ref']={'kind':'booking','id':str(ended_booking_id)}
                    payload['delivery']=issue(vendor_id,cid,int(ended_booking_id),'lock')
                    db.session.commit()
                _emit_to_kiosk(cid, 'session_expired', payload)
    except Exception:
        # An event failure must not turn a committed assignment into an API error.
        current_app.logger.exception('Dashboard kiosk state notification failed')
    finally:
        db.session.rollback()


def scanned_console_id(value, vendor_id):
    """Console id for a phone ticket start, from whatever the scanned PC QR held.

    The locked PC shows its signed cafe checkout URL (``...?qr=<token>``). The
    Hash app's ticket scanner forwards that raw value as ``console_id`` when it
    is not a number, so resolve it to the linked PC instead of rejecting it.
    A plain database console id (int or digit string) is used as before.
    """
    if isinstance(value, str):
        value = value.strip()
        if value.startswith('{'):
            import json
            try:
                parsed = json.loads(value)
            except ValueError:
                raise KioskError('invalid_pc_qr', 400)
            if not isinstance(parsed, dict):
                raise KioskError('invalid_pc_qr', 400)
            value = parsed.get('console_id', parsed.get('consoleId'))
            if isinstance(value, str):
                value = value.strip()
    try:
        return positive_id(value)
    except KioskError:
        if not isinstance(value, str) or not value:
            raise
    from app.controllers.cafe_wallet_controller import resolve_qr
    from app.services.cafe_wallet_service import CafeError
    try:
        link = resolve_qr(value)
    except CafeError as error:
        raise KioskError('pc_qr_expired' if error.status == 410 else 'invalid_pc_qr', error.status)
    if int(link.vendor_id) != int(vendor_id):
        raise KioskError('booking_scope_mismatch', 403)
    return positive_id(link.console_id)


def secure_start(fn=None, *, verify_only=False, phone=False):
    if fn is None:return lambda handler:secure_start(handler,verify_only=verify_only,phone=phone)
    @wraps(fn)
    def wrapped():
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            raise KioskError('invalid_json', 400)
        if phone:
            bid = positive_id(data.get('booking_id'))
            owner = db.session.execute(text('''SELECT ag.vendor_id FROM bookings b
                JOIN available_games ag ON ag.id=b.game_id WHERE b.id=:bid AND b.user_id=:uid'''),
                {'bid':bid,'uid':g.cafe_user_id}).first()
            if not owner: raise KioskError('booking_not_owned',403)
            identity = {'kind':'gamer','vendor_id':int(owner.vendor_id)}
            if data.get('additional_console_ids'): raise KioskError('invalid_console_ids',400)
        else:
            identity = runtime_identity()
        if verify_only and identity['kind']!='kiosk':raise KioskError('kiosk_token_required',403)
        if phone and data.get('console_id') is not None:
            console_id = scanned_console_id(data['console_id'], identity['vendor_id'])
        else:
            console_id = positive_id(data.get('console_id') or identity.get('console_id'))
        g.kiosk_diagnostic={'identity_kind':identity['kind'],'vendor_id':identity['vendor_id'],
            'linked_console_id':identity.get('console_id'),'requested_console_id':console_id}
        rate_limit(console_id)
        code = data.get('access_code') or data.get('accessCode')
        qr=data.get('qr')
        if not code and qr:
            import json
            if isinstance(qr,str):
                try:qr=json.loads(qr)
                except (ValueError,TypeError):qr={'access_code':qr}
            if not isinstance(qr,dict):raise KioskError('invalid_booking_qr',400)
            code=qr.get('access_code') or qr.get('accessCode')
            if qr.get('booking_id') is not None:
                if data.get('booking_id') is not None and str(data['booking_id'])!=str(qr['booking_id']):raise KioskError('booking_scope_mismatch',403)
                data['booking_id']=qr['booking_id']
        data['console_id']=console_id
        if identity['kind'] == 'kiosk' and not code:
            raise KioskError('access_code_required', 400)
        vendor_id = identity['vendor_id']
        check_scope(identity, vendor_id, console_id)
        vendor_lock(vendor_id)
        code_id = None
        redemption = None
        try:
            if code:
                if isinstance(code,str):code=code.strip().upper()
                if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isalnum():
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
                    SELECT b.id, b.user_id, b.game_id, ag.vendor_id, d.book_status, d.console_id,
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
                    SELECT b.id, b.user_id, b.game_id, ag.vendor_id, d.book_status, d.console_id,
                           d.date, d.start_time, d.end_time, b.status, b.squad_details
                    FROM bookings b JOIN available_games ag ON ag.id=b.game_id
                    JOIN VENDOR_{vendor_id}_DASHBOARD d ON d.book_id=b.id
                    WHERE b.id=:bid AND ag.vendor_id=:vid
                '''), {'bid': bid, 'vid': vendor_id}).mappings().first()
            if not target:
                raise KioskError('booking_not_found', 404)
            if phone and target['user_id'] != g.cafe_user_id:
                raise KioskError('booking_not_owned',403)
            g.kiosk_diagnostic.update(booking_id=int(target['id']),assigned_console_ids=sorted(assigned_consoles(target)))
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
                if not verify_only and window.get('delivery',{}).get('state')=='failed':
                    from app.services.pc_commands import issue
                    window['delivery']=issue(vendor_id,console_id,int(target['id']),retry_failed=True)
                    db.session.commit()
                    from app.services.websocket_service import _emit_to_kiosk
                    _emit_to_kiosk(console_id,'unlock_request',dict(window,type='unlock_request'))
                db.session.rollback()
                return jsonify(dict(status='success',data=window,**({'verified':True,'can_start':True} if verify_only else {}))), 200
            if target['status'] in ('pending_acceptance','pending_verified','verification_failed','rejected'):
                raise KioskError('booking_not_accepted',409)
            if target['status'] in ('cancelled', 'canceled') or target['book_status'] not in ('upcoming', 'current'):
                raise KioskError('session_ended', 409)
            if assigned_consoles(target) and console_id not in assigned_consoles(target):
                raise KioskError('booking_console_mismatch', 403)
            if target['book_status'] == 'current':
                window = booking_window(vendor_id, target['id'], console_id)
                if window['status'] != 'active':
                    raise KioskError('session_ended', 409)
            else:
                begin, finish = utc_window(target['date'], target['start_time'], target['end_time'])
                if not begin <= datetime.now(timezone.utc) < finish:
                    raise KioskError('session_not_active', 409)
            if verify_only:
                begin,finish=utc_window(target['date'],target['start_time'],target['end_time'])
                if target['book_status']=='current':
                    window=booking_window(vendor_id,target['id'],console_id)
                else:
                    window={'booking_id':int(target['id']),'console_id':console_id,'vendor_id':vendor_id,
                        'game_id':int(target['game_id']),'start_time':begin.isoformat(),'end_time':finish.isoformat(),
                        'status':'ready','server_time':datetime.now(timezone.utc).isoformat()}
                db.session.rollback()
                return jsonify(status='success',verified=True,can_start=True,data=window),200
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
            # Next slots the gamer already bought run on in this same session.
            adopt_follow_on_bookings(vendor_id, console_id=console_id)
            window = booking_window(vendor_id, target['id'], console_id)
            if window['status'] != 'active':
                raise KioskError('session_not_active', 409)
            from app.services.pc_commands import issue
            from app.services.session_extensions import ready,attach
            if ready():
                from app.models.console_link_session import ConsoleLinkSession
                link=ConsoleLinkSession.query.filter_by(vendor_id=vendor_id,console_id=console_id,status='active').first()
                if link:
                    attach(link,{'kind':'booking','id':str(target['id'])})
                    window=booking_window(vendor_id,target['id'],console_id)
            window['delivery']=issue(vendor_id,console_id,int(target['id'])) or {'state':'unconfirmed','acknowledged':False}
            window['session_ref']={'kind':'booking','id':str(target['id'])}
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


def heal_console_availability(vendor_id):
    """Free PCs whose busy flag outlived every session that could own them.

    Several end paths (app cancellation, canonical-status sync on the landing
    page, kiosk/QR reconcilers) close the booking without touching
    CONSOLE_AVAILABILITY, which left stations "Occupied" with no session.
    A console stays busy only while something live owns it: a current
    dashboard booking (direct or squad-assigned), an active/reserved QR play
    session, an open kiosk runtime session, or maintenance.
    Caller holds vendor_lock and owns the transaction.
    """
    vendor_id = positive_id(vendor_id)
    if db.engine.dialect.name != 'postgresql':
        return []

    def has(table):
        return bool(db.session.execute(text('SELECT to_regclass(:t)'), {'t': table}).scalar())

    qr_guard = """AND NOT EXISTS (SELECT 1 FROM cafe_play_sessions ps
              WHERE ps.vendor_id=:vid AND ps.console_id=ca.console_id
                AND (ps.state='active' OR (ps.state='reserved' AND ps.deadline>timezone('UTC', now()))))""" if has('cafe_play_sessions') else ''
    runtime_guard = """AND NOT EXISTS (SELECT 1 FROM kiosk_runtime_sessions rs
              WHERE rs.vendor_id=:vid AND rs.console_id=ca.console_id AND rs.ended_at IS NULL)""" if has('kiosk_runtime_sessions') else ''
    maintenance_guard = """AND NOT EXISTS (SELECT 1 FROM maintenance_status ms WHERE ms.console_id=ca.console_id
              AND lower(COALESCE(ms.available_status, '')) IN ('under maintenance', 'maintenance'))""" if has('maintenance_status') else ''
    rows = db.session.execute(text(f"""
        UPDATE VENDOR_{vendor_id}_CONSOLE_AVAILABILITY ca SET is_available=TRUE
        WHERE ca.is_available=FALSE
          {maintenance_guard}
          AND NOT EXISTS (
              SELECT 1 FROM VENDOR_{vendor_id}_DASHBOARD d LEFT JOIN bookings b ON b.id=d.book_id
              WHERE d.book_status='current' AND (d.console_id=ca.console_id OR EXISTS (
                  SELECT 1 FROM jsonb_array_elements_text(CASE
                      WHEN jsonb_typeof(b.squad_details::jsonb->'assigned_console_ids')='array'
                      THEN b.squad_details::jsonb->'assigned_console_ids' ELSE '[]'::jsonb END) a(cid)
                  WHERE a.cid ~ '^[0-9]+$' AND a.cid::int=ca.console_id)))
          {qr_guard}
          {runtime_guard}
        RETURNING ca.console_id
    """), {'vid': vendor_id}).scalars().all()
    return sorted(set(int(cid) for cid in rows))

# A gamer who buys the next slot back-to-back keeps playing: the follow-on
# booking joins the running session (same PC, same code) instead of waiting
# for a second scan. Pay-at-cafe slots still awaiting acceptance stay out.
ADOPTABLE_BOOKING_STATUSES = ('confirmed', 'checked_in')


def _is_squad(row):
    details = row.get('squad_details') or {}
    return bool(details.get('enabled')) and int(details.get('player_count') or 1) > 1


def adopt_follow_on_bookings(vendor_id, console_id=None):
    """Promote each live session's contiguous same-gamer, same-game upcoming
    bookings onto its PC and stretch the enrolled runtime to cover them.
    Caller holds vendor_lock and commits. Returns {console_id: [booking ids]}."""
    vendor_id = positive_id(vendor_id)
    table = f'VENDOR_{vendor_id}_DASHBOARD'
    now = datetime.now(timezone.utc)
    current = db.session.execute(text(f'''
        SELECT d.book_id, d.user_id, d.game_id, d.console_id, d.date, d.start_time, d.end_time,
               b.squad_details
        FROM {table} d JOIN bookings b ON b.id=d.book_id
        WHERE d.book_status='current' AND d.user_id IS NOT NULL
          AND b.status NOT IN ('cancelled','canceled','completed')
    ''')).mappings().all()
    chains = {}
    for row in current:
        consoles = assigned_consoles(row)
        if len(consoles) != 1 or _is_squad(row):
            continue  # Squads keep explicit desk starts.
        cid = next(iter(consoles))
        if console_id is not None and cid != int(console_id):
            continue
        try:
            _, finish = utc_window(row['date'], row['start_time'], row['end_time'])
        except KioskError:
            continue
        key = (int(row['user_id']), int(row['game_id']), cid)
        chain = chains.setdefault(key, {'end': finish, 'anchor': int(row['book_id'])})
        if finish > chain['end']:
            chain.update(end=finish, anchor=int(row['book_id']))
    # A session long past its end is stale, not live; never stretch it.
    chains = {k: v for k, v in chains.items() if v['end'] >= now - timedelta(minutes=30)}
    if not chains:
        return {}
    today = datetime.now(IST).date()
    upcoming = db.session.execute(text(f'''
        SELECT d.book_id, d.user_id, d.game_id, d.console_id, d.date, d.start_time, d.end_time,
               b.squad_details
        FROM {table} d JOIN bookings b ON b.id=d.book_id
        WHERE d.book_status='upcoming' AND d.user_id = ANY(:uids)
          AND d.date BETWEEN :d0 AND :d1 AND b.status IN :statuses
        ORDER BY d.date, d.start_time, d.book_id
    ''').bindparams(__import__('sqlalchemy').bindparam('statuses', expanding=True)),
        {'uids': sorted({k[0] for k in chains}), 'd0': today - timedelta(days=1),
         'd1': today + timedelta(days=1), 'statuses': list(ADOPTABLE_BOOKING_STATUSES)}).mappings().all()
    from app.routes import _share_chain_access_code
    adopted = {}
    for (uid, gid, cid), chain in chains.items():
        old_end = chain['end']
        for row in upcoming:
            if int(row['user_id']) != uid or int(row['game_id']) != gid or _is_squad(row):
                continue
            consoles = assigned_consoles(row)
            reserved = {int(c) for c in (row.get('squad_details') or {}).get('desk_console_ids', []) or []}
            if (consoles and consoles != {cid}) or (reserved and reserved != {cid}):
                continue
            try:
                begin, finish = utc_window(row['date'], row['start_time'], row['end_time'])
            except KioskError:
                continue
            if begin != chain['end'] or finish <= now:
                continue
            bid = int(row['book_id'])
            try:
                with db.session.begin_nested():
                    _share_chain_access_code([chain['anchor'], bid])
                    moved = db.session.execute(text(f'''UPDATE {table} SET book_status='current', console_id=:cid
                        WHERE book_id=:bid AND book_status='upcoming' '''), {'cid': cid, 'bid': bid}).rowcount
                    if moved != 1:
                        continue
                    db.session.execute(text("UPDATE bookings SET status='checked_in' WHERE id=:bid AND status IN :st")
                        .bindparams(__import__('sqlalchemy').bindparam('st', expanding=True)),
                        {'bid': bid, 'st': list(ADOPTABLE_BOOKING_STATUSES)})
                    import json
                    db.session.execute(text('''UPDATE bookings
                        SET squad_details = COALESCE(CAST(squad_details AS jsonb), '{}'::jsonb) || CAST(:patch AS jsonb)
                        WHERE id=:bid'''), {'bid': bid, 'patch': json.dumps({
                            'assigned_console_ids': [cid], 'assigned_at': datetime.utcnow().isoformat(),
                            'joined_session_of': chain['anchor']})})
            except Exception:
                # Another gamer holds this PC for that slot (console guard): leave it to the desk.
                current_app.logger.warning('Could not join booking %s to the session on console %s', bid, cid, exc_info=True)
                continue
            chain['end'] = finish
            chain['anchor'] = bid
            adopted.setdefault(cid, []).append(bid)
        if cid in adopted:
            _stretch_runtime(vendor_id, cid, uid, old_end, chain['end'], adopted[cid])
    if adopted:
        db.session.execute(text(f'UPDATE VENDOR_{vendor_id}_CONSOLE_AVAILABILITY SET is_available=FALSE WHERE console_id=ANY(:ids)'),
                           {'ids': sorted(adopted)})
        current_app.logger.info('Joined back-to-back bookings vendor=%s %s', vendor_id, adopted)
    return adopted


def _stretch_runtime(vendor_id, console_id, user_id, old_end, new_end, booking_ids):
    """Move the enrolled PC session's paid boundary to the end of the chain, so
    the kiosk keeps playing (it plays until reserved_until)."""
    if db.engine.dialect.name != 'postgresql' or not db.session.execute(text("SELECT to_regclass('kiosk_runtime_sessions')")).scalar():
        return
    from app.services.session_extensions import RuntimeSession, changed
    row = RuntimeSession.query.filter_by(vendor_id=vendor_id, console_id=console_id, ended_at=None,
                                         source_kind='booking', user_id=user_id).populate_existing().with_for_update().first()
    if not row:
        return
    old = old_end.astimezone(timezone.utc).replace(tzinfo=None)
    new = new_end.astimezone(timezone.utc).replace(tzinfo=None)
    # A paid extension already runs past the old slot end: that time is bought
    # twice, so leave it for staff rather than silently overlap billing.
    if row.reserved_until > old + timedelta(seconds=1) or row.stop_at is not None:
        current_app.logger.warning('Runtime %s already extended past %s; not stretching to %s', row.id, old, new)
        return
    row.paid_until = max(row.paid_until or new, new)
    row.reserved_until = new
    row.booking_ids = list(dict.fromkeys([*(row.booking_ids or []), *booking_ids]))
    if row.status == 'overtime_pending':
        row.status, row.reason = 'active', None
    row.notice_boundary = None
    changed(row)


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
        if row['booking_status'] in ('cancelled', 'canceled', 'completed'):
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
    joined = adopt_follow_on_bookings(vendor_id)
    healed = set(heal_console_availability(vendor_id)) - candidates
    db.session.commit()
    if joined:
        from app.routes import _invalidate_vendor_caches
        from app.services.websocket_service import socketio
        _invalidate_vendor_caches(vendor_id)
        for cid, ids in joined.items():
            # A refresh signal only: the dashboard reloads Live/Upcoming from the snapshot.
            socketio.emit('booking_queue_updated', {'vendorId': vendor_id, 'console_id': cid, 'booking_ids': ids,
                                                    'reason': 'joined_session'}, room=f'vendor_{vendor_id}')
    if expired or healed:
        from app.routes import _invalidate_vendor_caches
        from app.services.websocket_service import socketio, _emit_to_kiosk
        _invalidate_vendor_caches(vendor_id)
        for cid in candidates - occupied:
            _emit_to_kiosk(cid, 'session_expired', {'console_id': cid})
            socketio.emit('console_availability', {'vendorId': vendor_id, 'console_id': cid, 'is_available': True}, room=f'vendor_{vendor_id}')
        for cid in sorted(healed):
            current_app.logger.warning('Freed stale busy flag vendor=%s console=%s', vendor_id, cid)
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
