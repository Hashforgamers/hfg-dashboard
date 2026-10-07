"""Kiosk credentials, tenant checks and transaction-scoped retry protection."""
import hashlib
import json
from functools import wraps

import jwt
from flask import current_app, g, jsonify, make_response, request
from sqlalchemy import text
from werkzeug.exceptions import HTTPException

from app.extension.extensions import db


class KioskError(HTTPException):
    def __init__(self, code, status=401):
        super().__init__(description=code)
        self.code = status
        self.error_code = code


def positive_id(value):
    try:
        number = int(value)
        if isinstance(value, bool) or str(number) != str(value) or number <= 0:
            raise ValueError()
        return number
    except (ValueError, TypeError):
        raise KioskError('invalid_id', 400)


def bearer_token():
    header = request.headers.get('Authorization', '')
    return header[7:].strip() if header.startswith('Bearer ') else ''


def linked_identity(token):
    if not isinstance(token, str) or not token or len(token) > 128:
        raise KioskError('invalid_session_token')
    row = db.session.execute(text('''
        SELECT s.id, s.console_id, s.vendor_id, s.kiosk_id
        FROM console_link_sessions s
        JOIN consoles c ON c.id = s.console_id AND c.vendor_id = s.vendor_id
        WHERE s.session_token = :token AND s.status = 'active'
    '''), {'token': token}).mappings().first()
    if not row:
        raise KioskError('invalid_session_token')
    return dict(row, kind='kiosk')


def vendor_identity(token, permission='gaming.manage'):
    if not token:
        raise KioskError('token_required')
    try:
        claims = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'],
                            options={'verify_sub': False, 'require': ['exp', 'sub']})
    except jwt.ExpiredSignatureError:
        raise KioskError('token_expired')
    except jwt.InvalidTokenError:
        raise KioskError('token_invalid')
    subject = claims.get('sub')
    if isinstance(subject, dict) and subject.get('type') == 'vendor':
        vendor_id = positive_id(subject.get('id'))
    elif claims.get('scope') == 'vendor_access' and claims.get('type') == 'access':
        if permission not in (claims.get('staff') or {}).get('permissions', []):
            raise KioskError('permission_denied', 403)
        vendor_id = positive_id(claims.get('vendor_id'))
    else:
        raise KioskError('vendor_token_required', 403)
    return {'kind': 'vendor', 'vendor_id': vendor_id}


def runtime_identity():
    token = bearer_token()
    if not token:
        raise KioskError('token_required')
    # Link tokens are opaque; JWTs have exactly three dot-separated parts.
    return vendor_identity(token) if token.count('.') == 2 else linked_identity(token)


def check_scope(identity, vendor_id, console_id=None, game_id=None):
    vendor_id = positive_id(vendor_id)
    if identity['vendor_id'] != vendor_id:
        raise KioskError('vendor_mismatch', 403)
    if console_id is not None:
        console_id = positive_id(console_id)
        if identity['kind'] == 'kiosk' and identity['console_id'] != console_id:
            raise KioskError('console_mismatch', 403)
        found = db.session.execute(text('SELECT 1 FROM consoles WHERE id=:cid AND vendor_id=:vid'),
                                   {'cid': console_id, 'vid': vendor_id}).first()
        if not found:
            raise KioskError('console_mismatch', 403)
    if game_id is not None:
        found = db.session.execute(text('SELECT 1 FROM available_games WHERE id=:gid AND vendor_id=:vid'),
                                   {'gid': positive_id(game_id), 'vid': vendor_id}).first()
        if not found:
            raise KioskError('game_mismatch', 403)


def vendor_required(fn):
    @wraps(fn)
    def wrapped(vendor_id, *args, **kwargs):
        identity = vendor_identity(bearer_token())
        check_scope(identity, vendor_id)
        return fn(vendor_id, *args, **kwargs)
    return wrapped


def vendor_lock(vendor_id):
    # Shared by starts, releases and expiry. PostgreSQL releases on commit/rollback.
    db.session.execute(text('SELECT pg_advisory_xact_lock(220926, :vid)'), {'vid': positive_id(vendor_id)})


def rate_limit(console_id):
    # Separate transaction: rejected attempts must survive a booking rollback.
    # request.remote_addr is set by the trusted edge ProxyFix, never a caller-supplied custom header.
    keys = [('console:' + str(console_id), 10), ('ip:' + str(request.remote_addr), 60)]
    exceeded = False
    with db.engine.begin() as conn:
        for key, limit in keys:
            attempts = conn.execute(text('''
                INSERT INTO kiosk_rate_limits (key, window_start, attempts)
                VALUES (:key, clock_timestamp(), 1)
                ON CONFLICT (key) DO UPDATE SET
                  attempts = CASE WHEN kiosk_rate_limits.window_start <= clock_timestamp() - interval '1 minute'
                                  THEN 1 ELSE kiosk_rate_limits.attempts + 1 END,
                  window_start = CASE WHEN kiosk_rate_limits.window_start <= clock_timestamp() - interval '1 minute'
                                      THEN clock_timestamp() ELSE kiosk_rate_limits.window_start END
                RETURNING attempts
            '''), {'key': key}).scalar_one()
            exceeded = exceeded or attempts > limit
    if exceeded:
        raise KioskError('rate_limited', 429)


def transactional_device(fn):
    """Authenticate before legacy handlers; store success and mutation in one commit."""
    @wraps(fn)
    def wrapped(gameid, console_id, vendor_id, booking_id=None):
        identity = runtime_identity()
        vendor_id, console_id, gameid = map(positive_id, (vendor_id, console_id, gameid))
        check_scope(identity, vendor_id, console_id, gameid)
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            raise KioskError('invalid_json', 400)
        additional = body.get('additional_console_ids') or []
        if not isinstance(additional, list):
            raise KioskError('invalid_console_ids', 400)
        for cid in additional:
            check_scope(identity, vendor_id, cid, gameid)
        vendor_lock(vendor_id)
        key = request.headers.get('Idempotency-Key') or request.headers.get('X-Idempotency-Key')
        if key and len(key) > 128:
            raise KioskError('invalid_idempotency_key', 400)
        principal = f"{identity['kind']}:{identity.get('id', vendor_id)}"
        fingerprint = hashlib.sha256(json.dumps([request.path, body], sort_keys=True).encode()).hexdigest()
        if key:
            saved = db.session.execute(text('SELECT * FROM kiosk_idempotency WHERE principal=:p AND key=:k'),
                                       {'p': principal, 'k': key}).mappings().first()
            if saved:
                if saved['fingerprint'] != fingerprint:
                    raise KioskError('idempotency_conflict', 409)
                db.session.rollback()
                return jsonify(saved['response']), saved['status_code']
        g.kiosk_transaction = True
        try:
            release_bookings=[]
            if booking_id is None and db.session.execute(text("SELECT to_regclass('kiosk_runtime_sessions')")).scalar():
                release_bookings=db.session.execute(text(f"""SELECT DISTINCT b.id FROM bookings b
                    JOIN VENDOR_{vendor_id}_DASHBOARD d ON d.book_id=b.id
                    WHERE lower(d.book_status) IN ('current','active','checked_in')
                      AND (d.console_id=:cid OR COALESCE(b.squad_details::jsonb->'assigned_console_ids','[]'::jsonb) @> to_jsonb(CAST(:cid AS integer)))
                      AND NOT COALESCE(b.squad_details::jsonb->'released_console_ids','[]'::jsonb) @> to_jsonb(CAST(:cid AS integer))"""),{'cid':console_id}).scalars().all()
            # Release retries without keys may not terminate a newer booking.
            if identity['kind'] == 'kiosk':
                from app.services.kiosk_runtime import booking_window
                target = positive_id(booking_id or body.get('booking_id'))
                window = booking_window(vendor_id, target, console_id)
                if window['game_id'] != gameid:
                    raise KioskError('game_mismatch', 403)
                if booking_id is None and window['status'] != 'active':
                    response = make_response(jsonify({'status': 'success', 'message': 'Session already ended'}), 200)
                elif booking_id is None and window['status'] == 'active':
                    response = make_response(fn(gameid, console_id, vendor_id))
                elif booking_id is not None and window['status'] == 'active':
                    response = make_response(jsonify({'status': 'success', 'message': 'Session already started'}), 200)
                else:
                    raise KioskError('redeem_access_code_first', 409)
            else:
                args = dict(gameid=gameid, console_id=console_id, vendor_id=vendor_id)
                if booking_id is not None:
                    args['booking_id'] = positive_id(booking_id)
                response = make_response(fn(**args))
            if response.status_code >= 400:
                db.session.rollback()
                return response
            if booking_id is None:
                if db.session.execute(text("SELECT to_regclass('kiosk_runtime_sessions')")).scalar():
                    from app.services.session_extensions import RuntimeSession, lock_row, finish
                    running=RuntimeSession.query.filter_by(vendor_id=vendor_id,console_id=console_id,ended_at=None).first()
                    if running: finish(lock_row(running.id))
                    # A legacy squad sibling can share a booking with an enrolled PC.
                    from app.models.booking import Booking
                    from app.services.session_extensions import release_base_booking
                    from types import SimpleNamespace
                    for bid in release_bookings:
                        anchor_id=db.session.execute(text("SELECT id FROM kiosk_runtime_sessions WHERE vendor_id=:vid AND source_kind='booking' AND booking_ids::jsonb @> to_jsonb(CAST(:bid AS integer)) LIMIT 1"),{'vid':vendor_id,'bid':bid}).scalar()
                        anchor=db.session.get(RuntimeSession,anchor_id) if anchor_id else None
                        if not anchor: continue
                        booking=Booking.query.filter_by(id=bid).with_for_update().first()
                        details=dict(booking.squad_details or {})
                        assigned=set(map(int,details.get('assigned_console_ids',[]) or [console_id]))
                        released=set(map(int,details.get('released_console_ids',[])));released.add(console_id)
                        details['released_console_ids']=sorted(released)
                        release_base_booking(SimpleNamespace(id=anchor.id,vendor_id=vendor_id,console_id=console_id),booking,details,assigned,released)
                        booking.squad_details=details
            if key:
                db.session.execute(text('''INSERT INTO kiosk_idempotency
                    (principal, key, fingerprint, response, status_code)
                    VALUES (:p, :k, :f, CAST(:r AS jsonb), :s)'''),
                    {'p': principal, 'k': key, 'f': fingerprint,
                     'r': json.dumps(response.get_json()), 's': response.status_code})
            db.session.commit()
            from app.routes import _invalidate_vendor_caches
            _invalidate_vendor_caches(vendor_id)
            g.kiosk_transaction = False
            from app.services.kiosk_runtime import notify_console_runtime
            notify_console_runtime(vendor_id, [console_id] + additional)
            return response
        except Exception:
            db.session.rollback()
            raise
    return wrapped


def vendor_assignment(fn):
    """Protect the dashboard assignment path that can otherwise bypass redemption."""
    @wraps(fn)
    def wrapped():
        identity = vendor_identity(bearer_token())
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            raise KioskError('invalid_json', 400)
        vendor_id = positive_id(body.get('vendor_id'))
        game_id = positive_id(body.get('game_id'))
        console_id = positive_id(body.get('console_id'))
        additional = body.get('additional_console_ids') or []
        if not isinstance(additional, list):
            raise KioskError('invalid_console_ids', 400)
        for cid in [console_id] + additional:
            check_scope(identity, vendor_id, cid, game_id)
        # Normalize interpolated IDs before the legacy SQL helper sees them.
        body.update(vendor_id=vendor_id, game_id=game_id, console_id=console_id)
        vendor_lock(vendor_id)
        g.kiosk_transaction = True
        try:
            response = make_response(fn())
            if response.status_code >= 400:
                db.session.rollback()
            else:
                db.session.commit()
                from app.routes import _invalidate_vendor_caches
                _invalidate_vendor_caches(vendor_id)
                g.kiosk_transaction = False
                from app.services.kiosk_runtime import notify_console_runtime
                assigned = (response.get_json() or {}).get('assigned_console_ids')
                notify_console_runtime(vendor_id, assigned or [console_id] + additional)
            return response
        except Exception:
            db.session.rollback()
            raise
    return wrapped
