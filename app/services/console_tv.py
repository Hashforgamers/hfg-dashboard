"""Hash Console Lock (Smart TV) on the shared kiosk platform.

A TV is not a second backend. It is one more ``console_link_sessions`` row
(``device_type='CONSOLE_TV'``): the same opaque, revocable bearer credential the
PC kiosk uses, bound to exactly one cafe station. Sessions, timers, pricing,
extensions and billing stay in the shared runtime engine
(``session_extensions``/``kiosk_runtime``). This module only adds what a TV
needs on top:

* pairing (short-lived single-use code approved by a cafe admin),
* display-control commands (LOCK / UNLOCK / HDMI_TEST) whose *device-reported*
  result is stored apart from delivery, never inferred from an acknowledgement,
* a versioned event contract emitted only to TV links (``device_<link id>``
  room), so deployed PC kiosks see no new events,
* heartbeat / health, and backend-authoritative expiry for TV stations.

Everything is dormant until ``sql/20261123_console_tv_devices.sql`` has run.
"""
import hashlib
import hmac
import json
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from flask import current_app, request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extension.extensions import db
from app.services.kiosk_security import KioskError, bearer_token, positive_id

PC_KIOSK = 'PC_KIOSK'
CONSOLE_TV = 'CONSOLE_TV'
TV_PLATFORMS = ('ANDROID_TV', 'GOOGLE_TV', 'TIZEN', 'WEBOS')
CAPABILITIES = ('switchToApp', 'switchToHdmi', 'lockEnforcement')
LIFECYCLE = ('IDLE', 'ACTIVE', 'EXPIRING', 'EXPIRED', 'ENDED')
DISPLAY_STATUSES = ('NOT_REQUESTED', 'PENDING', 'SUCCEEDED', 'FAILED', 'UNSUPPORTED', 'UNVERIFIED')
RESULT_STATUSES = ('SUCCEEDED', 'FAILED', 'UNSUPPORTED', 'UNVERIFIED')
COMMAND_TYPES = ('LOCK', 'UNLOCK', 'HDMI_TEST')
COMMAND_EVENTS = {'LOCK': 'device.lock.requested', 'UNLOCK': 'device.unlock.requested',
                  'HDMI_TEST': 'device.hdmi_test.requested'}
# Which capability a command result is evidence for.
COMMAND_CAPABILITY = {'LOCK': 'lockEnforcement', 'UNLOCK': 'switchToHdmi', 'HDMI_TEST': 'switchToHdmi'}
REPORTED = {'SUCCEEDED': 'DEVICE_REPORTED_SUCCESS', 'FAILED': 'DEVICE_REPORTED_FAILURE',
            'UNSUPPORTED': 'UNSUPPORTED', 'UNVERIFIED': 'UNVERIFIED'}
CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'  # no 0/O, 1/I/L
CODE_LENGTH = 8
EXPIRING_SECONDS = 300  # the runtime engine's own 5-minute "time_low" boundary
RECENT_SESSION_SECONDS = 1800
INPUT_PATTERN = re.compile(r'^[A-Z0-9_]{1,32}$')
EVENT_VERSION = 1


# ---------------------------------------------------------------- helpers

def setting(name, default):
    try:
        return int(current_app.config.get(name) or default)
    except (TypeError, ValueError):
        return default


def pairing_ttl(): return setting('CONSOLE_TV_PAIRING_TTL_SECONDS', 300)
def claim_window(): return setting('CONSOLE_TV_CLAIM_WINDOW_SECONDS', 120)
def command_ttl(): return setting('CONSOLE_TV_COMMAND_TTL_SECONDS', 60)
def offline_after(): return setting('CONSOLE_TV_OFFLINE_AFTER_SECONDS', 45)
def heartbeat_interval(): return setting('CONSOLE_TV_HEARTBEAT_SECONDS', 15)


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def iso(value):
    return aware(value).isoformat().replace('+00:00', 'Z') if value else None


def ready():
    """True once the Console Lock migration ran (PostgreSQL only)."""
    try:
        if db.engine.dialect.name != 'postgresql':
            return False
        return bool(db.session.execute(text("SELECT to_regclass('device_commands')")).scalar())
    except Exception:
        return False


def _digest(kind, value):
    key = str(current_app.config.get('SECRET_KEY') or '').encode()
    return hmac.new(key, f'{kind}:{value}'.encode(), hashlib.sha256).hexdigest()


def client_ip():
    # Set by the trusted edge ProxyFix, never a caller-supplied header.
    return str(request.remote_addr or 'unknown')[:64]


def throttle(keys):
    """Shared fixed-window limiter (same table as kiosk code redemption).
    Runs in its own transaction so rejected attempts survive a rollback."""
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
                RETURNING attempts'''), {'key': key[:120]}).scalar_one()
            exceeded = exceeded or attempts > limit
    if exceeded:
        raise KioskError('rate_limited', 429)


def require_ready():
    if not ready():
        raise KioskError('console_tv_migration_required', 503)


def station_type(console_type):
    """Dashboard label: PC, PS5, PS4, XBOX, ... from consoles.console_type."""
    slug = re.sub(r'[^a-z0-9]', '', str(console_type or '').lower())
    if slug in ('pc', 'gamingpc') or slug.startswith('pc'):
        return 'PC'
    if slug.startswith('ps5') or slug == 'playstation5':
        return 'PS5'
    if slug.startswith('ps4') or slug == 'playstation4':
        return 'PS4'
    if slug.startswith('xbox'):
        return 'XBOX'
    if 'switch' in slug or 'nintendo' in slug:
        return 'SWITCH'
    if slug.startswith('vr') or 'quest' in slug:
        return 'VR'
    return (slug.upper() or 'UNKNOWN')[:16]


def _text(value, field, maximum=80):
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise KioskError(f'invalid_{field}', 400)
    return value.strip()


def normalize_input(value):
    if not isinstance(value, str):
        raise KioskError('invalid_hdmi_input', 400)
    candidate = value.strip().upper().replace('-', '_').replace(' ', '_')
    if not INPUT_PATTERN.match(candidate):
        raise KioskError('invalid_hdmi_input', 400)
    return candidate


def normalize_capabilities(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise KioskError('invalid_control_capabilities', 400)
    result = {}
    for name in CAPABILITIES:
        if name in value:
            if type(value[name]) is not bool:
                raise KioskError('invalid_control_capabilities', 400)
            result[name] = value[name]
    return result


def normalize_device(body):
    if not isinstance(body, dict):
        raise KioskError('invalid_json', 400)
    if body.get('deviceType', CONSOLE_TV) != CONSOLE_TV:
        raise KioskError('unsupported_device_type', 400)
    platform = body.get('tvPlatform')
    if platform not in TV_PLATFORMS:
        raise KioskError('invalid_tv_platform', 400)
    metadata = {'tvPlatform': platform}
    for field in ('tvManufacturer', 'tvModel', 'appVersion', 'osVersion', 'consoleType'):
        value = _text(body.get(field), field)
        if value is not None:
            metadata[field] = value
    if body.get('hdmiInput') is not None:
        metadata['hdmiInput'] = normalize_input(body['hdmiInput'])
    return metadata, normalize_capabilities(body.get('controlCapabilities')) or {}


def initial_verification(reported):
    now = iso(utcnow())
    return {name: {'status': 'UNSUPPORTED' if reported.get(name) is False else 'UNVERIFIED',
                   'source': 'device_reported' if name in reported else 'none', 'at': now}
            for name in CAPABILITIES}


def event(link, direction, kind, payload=None, runtime=None, actor=None, vendor_id=None, console_id=None):
    """Append-only device audit row (same transaction as the change it records)."""
    link = link or {}
    db.session.execute(text('''INSERT INTO device_events
        (vendor_id, console_id, link_id, runtime_id, session_version, direction, event_type, payload, actor)
        VALUES (:vid, :cid, :lid, :rid, :ver, :dir, :kind, CAST(:payload AS jsonb), :actor)'''),
        {'vid': link.get('vendor_id', vendor_id), 'cid': link.get('console_id', console_id), 'lid': link.get('id'),
         'rid': getattr(runtime, 'id', None), 'ver': getattr(runtime, 'revision', None), 'dir': direction,
         'kind': kind, 'payload': json.dumps(payload or {}, default=str), 'actor': (actor or {}).get('id')})


def cafe_audit(vendor_id, actor, action, details):
    """Mirror admin device actions into the existing cafe audit trail."""
    try:
        from app.services.cafe_wallet_service import audit
        audit(vendor_id, actor, action, details)
    except Exception:
        current_app.logger.warning('Cafe audit unavailable for %s', action, exc_info=True)


# ---------------------------------------------------------------- links

LINK_COLUMNS = '''s.id, s.vendor_id, s.console_id, s.kiosk_id, s.status, s.device_type, s.device_metadata,
    s.reported_capabilities, s.capability_verification, s.last_heartbeat_at, s.last_heartbeat,
    s.started_at, s.ended_at, s.close_reason, s.token_rotated_at, s.paired_by,
    c.console_type, c.console_number, c.model_number, c.configured_input_id'''


def _link(where, params):
    row = db.session.execute(text(f'''SELECT {LINK_COLUMNS} FROM console_link_sessions s
        JOIN consoles c ON c.id = s.console_id AND c.vendor_id = s.vendor_id WHERE {where}'''), params).mappings().first()
    return dict(row) if row else None


def device_link(token=None, require_tv=True):
    """Authenticate a device bearer token (same credential table as the PC kiosk)."""
    require_ready()
    token = token if token is not None else bearer_token()
    if not token:
        raise KioskError('token_required')
    if not isinstance(token, str) or len(token) > 128 or token.count('.') == 2:
        raise KioskError('invalid_session_token')
    link = _link("s.session_token = :token AND s.status = 'active'", {'token': token})
    if not link:
        raise KioskError('invalid_session_token')
    if require_tv and link['device_type'] != CONSOLE_TV:
        raise KioskError('console_tv_token_required', 403)
    return link


def link_by_id(link_id):
    return _link('s.id = :id', {'id': int(link_id)})


def device_type_of(link_id):
    if not ready():
        return PC_KIOSK
    value = db.session.execute(text('SELECT device_type FROM console_link_sessions WHERE id=:id'),
                               {'id': int(link_id)}).scalar()
    return value or PC_KIOSK


def link_for_identity(identity):
    """Socket identity -> active TV link (rechecked on every event)."""
    if not identity or identity.get('kind') != 'kiosk':
        raise KioskError('kiosk_token_required', 403)
    require_ready()
    link = _link("s.id = :id AND s.status = 'active'", {'id': int(identity['id'])})
    if not link:
        raise KioskError('invalid_session_token')
    if link['device_type'] != CONSOLE_TV:
        raise KioskError('console_tv_token_required', 403)
    return link


def is_online(link, now=None):
    seen_at = aware(link.get('last_heartbeat_at'))
    return bool(seen_at and seen_at > (now or utcnow()) - timedelta(seconds=offline_after()))


def device_view(link, now=None):
    metadata = link.get('device_metadata') or {}
    return {'deviceId': link['id'], 'deviceType': link['device_type'], 'status': link['status'],
            'tvPlatform': metadata.get('tvPlatform'), 'tvManufacturer': metadata.get('tvManufacturer'),
            'tvModel': metadata.get('tvModel'), 'appVersion': metadata.get('appVersion'),
            'reportedConsoleType': metadata.get('consoleType'),
            'controlCapabilities': link.get('reported_capabilities') or {},
            'capabilityVerification': link.get('capability_verification') or {},
            'online': is_online(link, now), 'lastHeartbeatAt': iso(link.get('last_heartbeat_at')),
            'heartbeat': link.get('last_heartbeat') or None, 'pairedAt': iso(link.get('started_at')),
            'credentialRotatedAt': iso(link.get('token_rotated_at'))}


def station_view(link_or_console):
    row = link_or_console
    console_id = row.get('console_id', row.get('id'))
    return {'stationId': console_id, 'stationNumber': row.get('console_number'),
            'stationName': (row.get('model_number') or '').strip() or f"Station {row.get('console_number')}",
            'consoleType': station_type(row.get('console_type')), 'rawConsoleType': row.get('console_type'),
            'hdmiInput': row.get('configured_input_id')}


# ---------------------------------------------------------------- pairing

def create_challenge(body):
    require_ready()
    throttle([('tvpair-ip:' + client_ip(), 10)])
    metadata, reported = normalize_device(body)
    db.session.execute(text("""UPDATE device_pairing_challenges SET status='expired'
        WHERE status IN ('pending','approved') AND expires_at <= CURRENT_TIMESTAMP"""))
    expires = utcnow() + timedelta(seconds=pairing_ttl())
    for _ in range(6):
        code = ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        secret = secrets.token_urlsafe(32)
        challenge_id = str(uuid.uuid4())
        try:
            with db.session.begin_nested():
                db.session.execute(text('''INSERT INTO device_pairing_challenges
                    (id, device_type, code_hash, claim_secret_hash, device_metadata, reported_capabilities,
                     created_ip, expires_at)
                    VALUES (:id, 'CONSOLE_TV', :code, :secret, CAST(:meta AS jsonb), CAST(:caps AS jsonb), :ip, :exp)'''),
                    {'id': challenge_id, 'code': _digest('pair', code), 'secret': _digest('claim', secret),
                     'meta': json.dumps(metadata), 'caps': json.dumps(reported), 'ip': client_ip(), 'exp': expires})
            break
        except IntegrityError:
            continue
    else:
        raise KioskError('pairing_unavailable', 503)
    event(None, 'system', 'device.pairing.requested', {'challengeId': challenge_id, 'tvPlatform': metadata['tvPlatform']})
    db.session.commit()
    return {'challengeId': challenge_id, 'pairingCode': f'{code[:4]}-{code[4:]}', 'claimSecret': secret,
            'expiresAt': iso(expires), 'serverTime': iso(utcnow()), 'pollIntervalSeconds': 3,
            'deviceType': CONSOLE_TV}


def normalize_code(value):
    if not isinstance(value, str):
        raise KioskError('invalid_pairing_code', 400)
    code = value.strip().upper().replace('-', '').replace(' ', '')
    if len(code) != CODE_LENGTH or any(ch not in CODE_ALPHABET for ch in code):
        raise KioskError('invalid_pairing_code', 400)
    return code


def _station_for_pairing(vendor_id, console_id):
    console = db.session.execute(text('''SELECT id, vendor_id, console_type, console_number, model_number, configured_input_id
        FROM consoles WHERE id=:cid AND vendor_id=:vid FOR UPDATE'''), {'cid': console_id, 'vid': vendor_id}).mappings().first()
    if not console:
        raise KioskError('console_mismatch', 403)
    if station_type(console['console_type']) == 'PC':
        raise KioskError('station_is_pc', 409)
    linked = db.session.execute(text("SELECT 1 FROM console_link_sessions WHERE console_id=:cid AND status='active' LIMIT 1"),
                                {'cid': console_id}).scalar()
    if linked:
        raise KioskError('station_already_paired', 409)
    return dict(console)


def approve_pairing(vendor_id, actor, body):
    """Cafe admin approves a code shown on the TV and picks the station. The
    vendor comes from the admin's token; the device never names a cafe."""
    require_ready()
    from app.services.kiosk_security import vendor_lock
    vendor_id = positive_id(vendor_id)
    throttle([(f'tvpair-approve:{vendor_id}', 20)])
    if not isinstance(body, dict):
        raise KioskError('invalid_json', 400)
    code = normalize_code(body.get('pairingCode'))
    console_id = positive_id(body.get('consoleId'))
    hdmi = normalize_input(body['hdmiInput']) if body.get('hdmiInput') is not None else None
    vendor_lock(vendor_id)
    console = _station_for_pairing(vendor_id, console_id)
    challenge = db.session.execute(text('''SELECT id, status, expires_at, device_metadata FROM device_pairing_challenges
        WHERE code_hash=:code AND status='pending' FOR UPDATE'''), {'code': _digest('pair', code)}).mappings().first()
    if not challenge or aware(challenge['expires_at']) <= utcnow():
        raise KioskError('pairing_code_not_found', 404)
    hdmi = hdmi or (challenge['device_metadata'] or {}).get('hdmiInput')
    db.session.execute(text('''UPDATE device_pairing_challenges SET status='approved', vendor_id=:vid, console_id=:cid,
        approved_by=:actor, approved_at=CURRENT_TIMESTAMP,
        expires_at=GREATEST(expires_at, CURRENT_TIMESTAMP + make_interval(secs => :window)) WHERE id=:id'''),
        {'vid': vendor_id, 'cid': console_id, 'actor': actor['id'], 'window': claim_window(), 'id': challenge['id']})
    if hdmi:
        db.session.execute(text('UPDATE consoles SET configured_input_id=:input WHERE id=:cid'), {'input': hdmi, 'cid': console_id})
    details = {'challengeId': str(challenge['id']), 'stationId': console_id, 'hdmiInput': hdmi}
    event(None, 'admin', 'device.pairing.approved', details, actor=actor, vendor_id=vendor_id, console_id=console_id)
    cafe_audit(vendor_id, actor, 'console_tv.pairing_approved', details)
    db.session.commit()
    return {'challengeId': str(challenge['id']), 'status': 'approved', 'station': station_view(dict(console, configured_input_id=hdmi or console['configured_input_id']))}


def claim_pairing(challenge_id, body):
    """TV exchanges its claim secret for a device credential, once, after approval."""
    require_ready()
    try:
        challenge_id = str(uuid.UUID(str(challenge_id)))
    except ValueError:
        raise KioskError('pairing_not_found', 404)
    throttle([('tvpair-claim:' + challenge_id, 40), ('tvpair-claim-ip:' + client_ip(), 120)])
    secret = (body or {}).get('claimSecret') if isinstance(body, dict) else None
    if not isinstance(secret, str) or not secret or len(secret) > 128:
        raise KioskError('pairing_not_found', 404)
    row = db.session.execute(text('SELECT * FROM device_pairing_challenges WHERE id=:id FOR UPDATE'),
                             {'id': challenge_id}).mappings().first()
    if not row or not hmac.compare_digest(row['claim_secret_hash'], _digest('claim', secret)):
        raise KioskError('pairing_not_found', 404)
    if row['status'] == 'claimed':
        raise KioskError('pairing_already_claimed', 410)
    if row['status'] in ('expired', 'rejected') or aware(row['expires_at']) <= utcnow():
        db.session.execute(text("UPDATE device_pairing_challenges SET status='expired' WHERE id=:id AND status IN ('pending','approved')"),
                           {'id': challenge_id})
        db.session.commit()
        raise KioskError('pairing_expired', 410)
    if row['status'] == 'pending':
        db.session.rollback()
        return 202, {'status': 'pending', 'challengeId': challenge_id, 'expiresAt': iso(row['expires_at']),
                     'serverTime': iso(utcnow()), 'pollIntervalSeconds': 3}
    from app.services.kiosk_security import vendor_lock
    vendor_lock(row['vendor_id'])
    try:
        console = _station_for_pairing(row['vendor_id'], row['console_id'])
    except KioskError:
        db.session.rollback()
        db.session.execute(text("UPDATE device_pairing_challenges SET status='rejected' WHERE id=:id"), {'id': challenge_id})
        db.session.commit()
        raise KioskError('station_already_paired', 409)
    token = secrets.token_urlsafe(32)
    reported = row['reported_capabilities'] or {}
    link_id = db.session.execute(text('''INSERT INTO console_link_sessions
        (vendor_id, console_id, kiosk_id, session_token, status, started_at, device_type, device_metadata,
         reported_capabilities, capability_verification, paired_by)
        VALUES (:vid, :cid, :kiosk, :token, 'active', CURRENT_TIMESTAMP, 'CONSOLE_TV', CAST(:meta AS jsonb),
                CAST(:caps AS jsonb), CAST(:verify AS jsonb), :by) RETURNING id'''),
        {'vid': row['vendor_id'], 'cid': row['console_id'], 'kiosk': 'tv-' + challenge_id[:20], 'token': token,
         'meta': json.dumps(row['device_metadata'] or {}), 'caps': json.dumps(reported),
         'verify': json.dumps(initial_verification(reported)), 'by': row['approved_by']}).scalar_one()
    db.session.execute(text("UPDATE device_pairing_challenges SET status='claimed', link_id=:lid, claimed_at=CURRENT_TIMESTAMP WHERE id=:id"),
                       {'lid': link_id, 'id': challenge_id})
    link = link_by_id(link_id)
    event(link, 'system', 'device.paired', {'challengeId': challenge_id})
    db.session.commit()
    notify_vendor(link, 'paired')
    return 200, {'status': 'paired', 'deviceToken': token, 'deviceId': link_id, 'vendorId': link['vendor_id'],
                 'station': station_view(link), 'device': device_view(link),
                 'wsUrl': current_app.config.get('KIOSK_WS_URL') or request.host_url.rstrip('/'),
                 'socketPath': '/socket.io', 'heartbeatIntervalSeconds': heartbeat_interval(),
                 'serverTime': iso(utcnow())}


def rotate_credential(link):
    """Replace the bearer in place: the link id (and any running session bound
    to it) is unchanged, the old token stops working immediately."""
    token = secrets.token_urlsafe(32)
    db.session.execute(text("UPDATE console_link_sessions SET session_token=:t, token_rotated_at=CURRENT_TIMESTAMP WHERE id=:id AND status='active'"),
                       {'t': token, 'id': link['id']})
    event(link, 'in', 'device.credential.rotated', {})
    db.session.commit()
    return {'deviceToken': token, 'deviceId': link['id'], 'rotatedAt': iso(utcnow())}


# ---------------------------------------------------------------- sessions

def runtime_model():
    from app.models.session_extension import RuntimeSession
    return RuntimeSession


def active_runtime(link_id):
    RuntimeSession = runtime_model()
    return (RuntimeSession.query.filter_by(link_id=link_id, ended_at=None)
            .order_by(RuntimeSession.started_at.desc()).first())


def current_runtime(link_id, now=None):
    """The running session, else one that ended recently (EXPIRED/ENDED screen)."""
    row = active_runtime(link_id)
    if row:
        return row
    RuntimeSession = runtime_model()
    cutoff = (now or utcnow()).replace(tzinfo=None) - timedelta(seconds=RECENT_SESSION_SECONDS)
    row = (RuntimeSession.query.filter(RuntimeSession.link_id == link_id, RuntimeSession.ended_at.isnot(None),
                                       RuntimeSession.ended_at >= cutoff)
           .order_by(RuntimeSession.ended_at.desc()).first())
    if row and RuntimeSession.query.filter(RuntimeSession.console_id == row.console_id,
                                           RuntimeSession.ended_at.is_(None)).first():
        return None  # another session already owns this station
    return row


def play_end(row):
    return min(row.reserved_until, row.stop_at) if row.stop_at else row.reserved_until


def lifecycle(row, now=None):
    if row is None:
        return 'IDLE'
    now = now or utcnow()
    if row.ended_at:
        return 'EXPIRED' if aware(row.ended_at) >= aware(row.reserved_until) - timedelta(seconds=1) else 'ENDED'
    end = aware(play_end(row))
    if now >= end:
        return 'EXPIRED'
    if (end - now).total_seconds() <= EXPIRING_SECONDS:
        return 'EXPIRING'
    return 'ACTIVE'


def session_contract(row, now=None):
    """Backend-authoritative timer. The TV counts down locally from expiresAt
    against serverTime and reconciles; it never extends play on its own."""
    if row is None:
        return None
    now = now or utcnow()
    state = lifecycle(row, now)
    end = play_end(row)
    playing = state in ('ACTIVE', 'EXPIRING')
    return {'sessionId': row.id, 'sessionRef': {'kind': row.source_kind, 'id': str(row.source_id)},
            'status': state, 'startedAt': iso(row.started_at), 'expiresAt': iso(end), 'endedAt': iso(row.ended_at),
            'serverTime': iso(now), 'version': row.revision, 'eventSequence': row.event_sequence,
            'playAllowed': playing,
            'secondsRemaining': max(0, int((aware(end) - now).total_seconds())) if playing else 0,
            'runtimeState': row.status, 'bookingIds': [int(b) for b in (row.booking_ids or [])],
            'stationId': row.console_id, 'deviceId': row.link_id}


def ensure_runtime(link):
    """A booking already running on this station when the TV (re)connects is
    enrolled in the shared engine, exactly as the PC kiosk start path does."""
    if active_runtime(link['id']):
        return
    try:
        from app.services.kiosk_runtime import assigned_consoles, booking_window
        from app.services.session_extensions import attach, ready as runtime_ready
        if not runtime_ready():
            return
        rows = db.session.execute(text(f"""SELECT d.*, b.squad_details FROM VENDOR_{positive_id(link['vendor_id'])}_DASHBOARD d
            JOIN bookings b ON b.id=d.book_id WHERE d.book_status='current' AND b.status NOT IN ('cancelled','canceled')
            ORDER BY d.date, d.start_time, d.book_id""")).mappings().all()
        for row in rows:
            if link['console_id'] not in assigned_consoles(row):
                continue
            window = booking_window(link['vendor_id'], row['book_id'], link['console_id'])
            if window['status'] == 'active':
                with db.session.begin_nested():
                    attach(SimpleNamespace(id=link['id'], vendor_id=link['vendor_id'], console_id=link['console_id']),
                           {'kind': 'booking', 'id': str(window['booking_id'])})
                db.session.commit()
                return
    except Exception:
        db.session.rollback()
        current_app.logger.warning('Console TV session enrolment skipped link=%s', link['id'], exc_info=True)


def expiry_due(row, now):
    """Console TV stations stop at the authorized end. The station is meant to
    be locked from then on, so no overtime is metered (PC kiosks keep their
    existing overtime handling)."""
    if row.ended_at or now < row.reserved_until or not ready():
        return False
    return device_type_of(row.link_id) == CONSOLE_TV


# ---------------------------------------------------------------- commands

def _command(command_id=None, where=None, params=None):
    if command_id:
        where, params = 'id=:id', {'id': str(command_id)}
    row = db.session.execute(text(f'SELECT * FROM device_commands WHERE {where} LIMIT 1'), params).mappings().first()
    return dict(row) if row else None


def command_payload(cmd, link=None, runtime=None):
    link = link or link_by_id(cmd['link_id'])
    data = {'v': EVENT_VERSION, 'eventId': str(uuid.uuid4()), 'type': COMMAND_EVENTS[cmd['command_type']],
            'commandId': str(cmd['id']), 'commandType': cmd['command_type'], 'commandStatus': cmd['command_status'],
            'deviceId': cmd['link_id'], 'stationId': cmd['console_id'], 'vendorId': cmd['vendor_id'],
            'sessionId': cmd['runtime_id'], 'sessionVersion': cmd['session_version'],
            'issuedAt': iso(cmd['issued_at']), 'expiresAt': iso(cmd['expires_at']), 'reason': cmd['reason'],
            'serverTime': iso(utcnow())}
    if cmd['command_type'] in ('UNLOCK', 'HDMI_TEST'):
        data['hdmiInput'] = (link or {}).get('configured_input_id')
    if runtime is None and cmd['runtime_id']:
        runtime = db.session.get(runtime_model(), cmd['runtime_id'])
    data['session'] = session_contract(runtime) if runtime is not None else None
    return data


def issue_command(link, command_type, runtime=None, reason=None, actor=None, dedupe_key=None):
    """Record a display command. Newer LOCK/UNLOCK supersedes older pending
    ones, so a delayed result can never apply an outdated decision."""
    if command_type not in COMMAND_TYPES:
        raise KioskError('invalid_command_type', 400)
    if command_type in ('LOCK', 'UNLOCK'):
        db.session.execute(text("""UPDATE device_commands SET command_status='SUPERSEDED', completed_at=CURRENT_TIMESTAMP
            WHERE link_id=:lid AND command_type IN ('LOCK','UNLOCK') AND command_status='PENDING'
              AND dedupe_key IS DISTINCT FROM :key"""), {'lid': link['id'], 'key': dedupe_key})
    command_id = str(uuid.uuid4())
    inserted = db.session.execute(text('''INSERT INTO device_commands
        (id, vendor_id, console_id, link_id, runtime_id, session_version, command_type, reason, issued_by, dedupe_key, expires_at)
        VALUES (:id, :vid, :cid, :lid, :rid, :ver, :type, :reason, :by, :key, CURRENT_TIMESTAMP + make_interval(secs => :ttl))
        ON CONFLICT (dedupe_key) DO NOTHING RETURNING id'''),
        {'id': command_id, 'vid': link['vendor_id'], 'cid': link['console_id'], 'lid': link['id'],
         'rid': getattr(runtime, 'id', None), 'ver': getattr(runtime, 'revision', None), 'type': command_type,
         'reason': (reason or '')[:48] or None, 'by': (actor or {}).get('id'), 'key': dedupe_key,
         'ttl': command_ttl()}).scalar()
    if not inserted:
        return None  # already issued for this session transition
    cmd = _command(command_id)
    event(link, 'out', COMMAND_EVENTS[command_type], {'commandId': command_id, 'reason': reason},
          runtime=runtime, actor=actor)
    return command_payload(cmd, link, runtime)


def pending_commands(link):
    db.session.execute(text("""UPDATE device_commands SET command_status='EXPIRED', completed_at=CURRENT_TIMESTAMP,
        failure_reason='no_result_before_expiry' WHERE link_id=:lid AND command_status='PENDING' AND expires_at <= CURRENT_TIMESTAMP"""),
        {'lid': link['id']})
    rows = db.session.execute(text("""SELECT * FROM device_commands WHERE link_id=:lid AND command_status='PENDING'
        ORDER BY issued_at"""), {'lid': link['id']}).mappings().all()
    return [command_payload(dict(r), link) for r in rows]


def _verify_capability(link, command_type, status, staff=None, actor=None):
    name = COMMAND_CAPABILITY[command_type]
    current = (link.get('capability_verification') or {}).get(name) or {}
    now = iso(utcnow())
    if staff is not None:
        value = {'status': 'STAFF_CONFIRMED' if staff else 'STAFF_REJECTED', 'source': 'staff', 'at': now,
                 'by': (actor or {}).get('id'), 'lastDeviceResult': current.get('lastDeviceResult')}
    elif current.get('status') in ('STAFF_CONFIRMED', 'STAFF_REJECTED'):
        value = dict(current, lastDeviceResult={'status': status, 'at': now})
    else:
        value = {'status': REPORTED[status], 'source': 'device_reported', 'at': now,
                 'lastDeviceResult': {'status': status, 'at': now}}
    db.session.execute(text('''UPDATE console_link_sessions SET capability_verification =
        COALESCE(capability_verification, '{}'::jsonb) || jsonb_build_object(CAST(:name AS text), CAST(:value AS jsonb)) WHERE id=:id'''),
        {'name': name, 'value': json.dumps(value), 'id': link['id']})


def record_result(link, body):
    """Store what the TV says happened. RECEIVED is delivery only; SUCCEEDED
    is the device's own report and is labelled as such everywhere."""
    if not isinstance(body, dict):
        raise KioskError('invalid_json', 400)
    try:
        command_id = str(uuid.UUID(str(body.get('commandId'))))
    except ValueError:
        raise KioskError('invalid_command_id', 400)
    status = body.get('status')
    if status not in RESULT_STATUSES + ('RECEIVED',):
        raise KioskError('invalid_result_status', 400)
    cmd = db.session.execute(text('SELECT * FROM device_commands WHERE id=:id FOR UPDATE'), {'id': command_id}).mappings().first()
    if not cmd or cmd['link_id'] != link['id']:
        raise KioskError('command_scope_mismatch', 403)
    cmd = dict(cmd)
    if body.get('sessionVersion') is not None and cmd['session_version'] is not None and body['sessionVersion'] != cmd['session_version']:
        raise KioskError('session_version_mismatch', 409)
    if status == 'RECEIVED':
        db.session.execute(text('UPDATE device_commands SET received_at=COALESCE(received_at, CURRENT_TIMESTAMP) WHERE id=:id'), {'id': command_id})
        event(link, 'in', 'device.control.received', {'commandId': command_id})
        return {'commandId': command_id, 'commandStatus': cmd['command_status'], 'received': True}, []
    if cmd['command_status'] in RESULT_STATUSES:
        if cmd['command_status'] == status:
            return {'commandId': command_id, 'commandStatus': status, 'duplicate': True}, []
        raise KioskError('result_conflict', 409)
    if cmd['command_status'] == 'SUPERSEDED':
        event(link, 'in', 'device.control.stale_result', {'commandId': command_id, 'status': status})
        db.session.commit()
        raise KioskError('stale_command', 409)
    if cmd['command_status'] == 'EXPIRED' or aware(cmd['expires_at']) <= utcnow():
        db.session.execute(text("""UPDATE device_commands SET command_status='EXPIRED', completed_at=COALESCE(completed_at, CURRENT_TIMESTAMP),
            failure_reason=COALESCE(failure_reason, 'result_after_expiry') WHERE id=:id"""), {'id': command_id})
        event(link, 'in', 'device.control.expired_result', {'commandId': command_id, 'status': status})
        db.session.commit()
        raise KioskError('command_expired', 409)
    detail = _text(body.get('detail'), 'detail', 200)
    observed = {}
    if body.get('observedInput') is not None:
        observed['observedInput'] = _text(body.get('observedInput'), 'observed_input', 32)
    for flag in ('lockScreenVisible', 'appInForeground'):
        if body.get(flag) is not None:
            if type(body[flag]) is not bool:
                raise KioskError('invalid_' + flag, 400)
            observed[flag] = body[flag]
    observed.update(status=status, detail=detail, evidence='device_reported', reportedAt=iso(utcnow()))
    db.session.execute(text('''UPDATE device_commands SET command_status=:status, completed_at=CURRENT_TIMESTAMP,
        received_at=COALESCE(received_at, CURRENT_TIMESTAMP), failure_reason=:reason, result=CAST(:result AS jsonb)
        WHERE id=:id'''), {'status': status, 'reason': None if status == 'SUCCEEDED' else (detail or status.lower()),
                            'result': json.dumps(observed), 'id': command_id})
    _verify_capability(link, cmd['command_type'], status)
    event(link, 'in', 'device.control.result', {'commandId': command_id, 'commandType': cmd['command_type'], **observed})
    follow_up = []
    if cmd['command_type'] == 'UNLOCK' and status != 'FAILED':
        # A late UNLOCK must never reopen a station whose session has ended.
        runtime = active_runtime(link['id'])
        if runtime is None or lifecycle(runtime) not in ('ACTIVE', 'EXPIRING'):
            lock = issue_command(link, 'LOCK', runtime=current_runtime(link['id']), reason='stale_unlock')
            if lock:
                follow_up.append(lock)
    return {'commandId': command_id, 'commandStatus': status, 'evidence': 'device_reported'}, follow_up


def display_state(link, runtime=None, now=None):
    now = now or utcnow()
    latest = db.session.execute(text("""SELECT * FROM device_commands WHERE link_id=:lid AND command_type IN ('LOCK','UNLOCK')
        AND command_status <> 'SUPERSEDED' ORDER BY issued_at DESC LIMIT 1"""), {'lid': link['id']}).mappings().first()

    def last(kind):
        row = db.session.execute(text("""SELECT id, completed_at FROM device_commands WHERE link_id=:lid AND command_type=:t
            AND command_status='SUCCEEDED' ORDER BY completed_at DESC LIMIT 1"""), {'lid': link['id'], 't': kind}).mappings().first()
        return {'commandId': str(row['id']), 'completedAt': iso(row['completed_at']), 'evidence': 'device_reported'} if row else None

    test = db.session.execute(text("""SELECT * FROM device_commands WHERE link_id=:lid AND command_type='HDMI_TEST'
        ORDER BY issued_at DESC LIMIT 1"""), {'lid': link['id']}).mappings().first()
    status = 'NOT_REQUESTED'
    if latest:
        status = latest['command_status']
        if status == 'PENDING' and aware(latest['expires_at']) <= now:
            status = 'EXPIRED'
        status = 'FAILED' if status == 'EXPIRED' else status
    state = lifecycle(runtime, now)
    authorized = state in ('ACTIVE', 'EXPIRING')
    lock_capable = (link.get('reported_capabilities') or {}).get('lockEnforcement') is True
    locked = bool(latest and latest['command_type'] == 'LOCK' and status == 'SUCCEEDED')
    if authorized:
        security, warning = 'SESSION_ACTIVE', None
    elif locked and lock_capable:
        security, warning = 'SECURE', None
    else:
        security = 'NOT_SECURE'
        warning = ('TV has not reported a successful lock' if not locked else
                   'TV reported the lock screen but does not claim it can enforce it')
        if not is_online(link, now):
            warning += '; TV is offline'
    return {'controlStatus': status,
            'lockState': ('LOCKED' if locked else 'UNLOCKED' if latest and latest['command_type'] == 'UNLOCK' and status == 'SUCCEEDED' else 'UNKNOWN'),
            'lastCommand': ({'commandId': str(latest['id']), 'commandType': latest['command_type'], 'commandStatus': status,
                             'issuedAt': iso(latest['issued_at']), 'completedAt': iso(latest['completed_at']),
                             'failureReason': latest['failure_reason'], 'reason': latest['reason']} if latest else None),
            'lastSuccessfulLock': last('LOCK'), 'lastSuccessfulUnlock': last('UNLOCK'),
            'lastHdmiTest': ({'commandId': str(test['id']), 'commandStatus': test['command_status'],
                              'issuedAt': iso(test['issued_at']), 'completedAt': iso(test['completed_at']),
                              'staffVerification': test['staff_verification'], 'result': test['result']} if test else None),
            'securelyLocked': security == 'SECURE', 'security': security, 'warning': warning}


# ---------------------------------------------------------------- events

def envelope(kind, link, row=None, contract=None, **extra):
    now = utcnow()
    data = {'v': EVENT_VERSION, 'eventId': str(uuid.uuid4()), 'type': kind, 'deviceId': link['id'],
            'stationId': link['console_id'], 'vendorId': link['vendor_id'],
            'sessionId': getattr(row, 'id', None), 'sessionVersion': getattr(row, 'revision', None),
            'eventSequence': getattr(row, 'event_sequence', None), 'issuedAt': iso(now), 'serverTime': iso(now),
            'session': contract}
    data.update(extra)
    return data


def _session_event_kind(row, contract):
    previous = db.session.execute(text("""SELECT event_type, payload FROM device_events WHERE runtime_id=:rid
        AND direction='out' AND event_type LIKE 'session.%' ORDER BY id DESC LIMIT 1"""), {'rid': row.id}).mappings().first()
    state = contract['status']
    before = (previous['payload'] or {}).get('session') or {} if previous else {}
    if state == 'ENDED':
        kind = 'session.ended'
    elif state == 'EXPIRED':
        kind = 'session.expired'
    elif previous is None:
        kind = 'session.started'
    elif before.get('expiresAt') and contract['expiresAt'] and contract['expiresAt'] > before['expiresAt']:
        kind = 'session.extended'
    elif state == 'EXPIRING' and before.get('status') != 'EXPIRING':
        kind = 'session.expiring'
    else:
        kind = 'session.updated'
    if previous is not None and kind in ('session.ended', 'session.expired') and previous['event_type'] == kind:
        kind = 'session.updated'
    return kind


def on_runtime_event(row, outbox):
    """Called by the shared engine's outbox dispatcher (same transaction, before
    the outbox row is marked published). Returns emits to send after commit."""
    if not ready():
        return []
    link = link_by_id(row.link_id)
    if not link or link['device_type'] != CONSOLE_TV or link['status'] != 'active':
        return []
    RuntimeSession = runtime_model()
    other = RuntimeSession.query.filter(RuntimeSession.console_id == row.console_id, RuntimeSession.ended_at.is_(None),
                                        RuntimeSession.id != row.id).first()
    if other is not None:
        return []  # a newer session owns this station; never lock its player out
    contract = session_contract(row)
    kind = _session_event_kind(row, contract)
    payload = envelope(kind, link, row, contract, outboxEventId=outbox.id if outbox is not None else None)
    event(link, 'out', kind, payload, runtime=row)
    emits = [(kind, payload)]
    if contract['status'] in ('EXPIRED', 'ENDED'):
        command = issue_command(link, 'LOCK', runtime=row, reason='session_' + contract['status'].lower(),
                                dedupe_key=f"{link['id']}:LOCK:{row.id}:end")
    else:
        command = issue_command(link, 'UNLOCK', runtime=row, reason='session_started',
                                dedupe_key=f"{link['id']}:UNLOCK:{row.id}:start")
    if command:
        emits.append((command['type'], command))
    return [(link, emits)]


def on_legacy_kiosk_event(console_id, name, data):
    """The PC kiosk path published unlock_request / session_expired for a
    station. A paired TV gets the same decision through the shared engine.
    Runs on its own app context (never touches the caller's transaction)."""
    if name not in ('unlock_request', 'session_expired'):
        return
    try:
        from app.services.websocket_service import socketio
        app = current_app._get_current_object()
        socketio.start_background_task(_legacy_bridge, app, int(console_id), name, dict(data or {}))
    except Exception:
        current_app.logger.exception('Console TV bridge could not start console=%s', console_id)


def _legacy_bridge(app, console_id, name, data, delay=0.3):
    from app.services.websocket_service import socketio
    if delay:
        socketio.sleep(delay)  # let the caller's commit land first
    with app.app_context():
        try:
            bridge_legacy_event(console_id, name, data)
        finally:
            db.session.remove()


def bridge_legacy_event(console_id, name, data):
    if not ready():
        return
    try:
        ids = db.session.execute(text("""SELECT id FROM console_link_sessions WHERE console_id=:cid AND status='active'
            AND device_type='CONSOLE_TV'"""), {'cid': int(console_id)}).scalars().all()
        db.session.rollback()
        if not ids:
            return
        from app.services.session_extensions import dispatch
        dispatch()  # runtime events -> session.* + UNLOCK/LOCK for the TV
        if name != 'session_expired':
            return
        emits = []
        for link_id in ids:
            link = link_by_id(link_id)
            if not link or active_runtime(link_id):
                continue
            minute = utcnow().strftime('%Y%m%d%H%M')
            command = issue_command(link, 'LOCK', runtime=current_runtime(link_id), reason=(data or {}).get('reason') or 'session_ended',
                                    dedupe_key=f'{link_id}:LOCK:idle:{minute}')
            if command:
                emits.append((link, [(command['type'], command)]))
        db.session.commit()
        publish(emits)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Console TV legacy event bridge failed console=%s', console_id)


def publish(emits):
    if not emits:
        return
    from app.services.websocket_service import socketio
    for link, items in emits:
        for name, payload in items:
            try:
                socketio.emit(name, payload, room=f"device_{link['id']}")
            except Exception:
                current_app.logger.exception('Console TV emit failed link=%s event=%s', link['id'], name)
        notify_vendor(link, 'session' if any(n.startswith('session.') for n, _ in items) else 'command')


def notify_vendor(link, reason):
    """Refresh signal for the dashboard; carries no player or financial data."""
    try:
        from app.services.websocket_service import socketio
        socketio.emit('console_device.updated', {'vendor_id': link['vendor_id'], 'console_id': link['console_id'],
                                                 'device_id': link['id'], 'reason': reason, 'server_time': iso(utcnow())},
                      room=f"vendor_{link['vendor_id']}")
    except Exception:
        current_app.logger.exception('Console TV vendor notification failed')


def send_to_device(link, name, payload):
    try:
        from app.services.websocket_service import socketio
        socketio.emit(name, payload, room=f"device_{link['id']}")
    except Exception:
        current_app.logger.exception('Console TV emit failed link=%s event=%s', link['id'], name)


# ---------------------------------------------------------------- device API

def device_state(link):
    """REST reconciliation: everything the TV needs after (re)connecting."""
    ensure_runtime(link)
    now = utcnow()
    runtime = current_runtime(link['id'], now)
    commands = pending_commands(link)
    state = {'serverTime': iso(now), 'device': device_view(link, now), 'station': station_view(link),
             'session': session_contract(runtime, now), 'display': display_state(link, runtime, now),
             'pendingCommands': commands, 'heartbeatIntervalSeconds': heartbeat_interval(),
             'eventVersion': EVENT_VERSION}
    db.session.commit()
    return state


def heartbeat(link, body):
    if body is not None and not isinstance(body, dict):
        raise KioskError('invalid_json', 400)
    body = body or {}
    beat = {}
    for field, size in (('appVersion', 40), ('currentInput', 32), ('networkType', 20), ('lockScreen', 32)):
        value = _text(body.get(field), field, size)
        if value is not None:
            beat[field] = value
    for flag in ('lockScreenVisible', 'appInForeground'):
        if body.get(flag) is not None:
            if type(body[flag]) is not bool:
                raise KioskError('invalid_' + flag, 400)
            beat[flag] = body[flag]
    if body.get('uptimeSeconds') is not None:
        if type(body['uptimeSeconds']) is not int or body['uptimeSeconds'] < 0:
            raise KioskError('invalid_uptimeSeconds', 400)
        beat['uptimeSeconds'] = body['uptimeSeconds']
    capabilities = normalize_capabilities(body.get('controlCapabilities'))
    was_online = is_online(link)
    beat['receivedAt'] = iso(utcnow())
    db.session.execute(text('''UPDATE console_link_sessions SET last_heartbeat_at=CURRENT_TIMESTAMP, last_heartbeat=CAST(:beat AS jsonb),
        reported_capabilities=CASE WHEN CAST(:caps AS jsonb) IS NULL THEN reported_capabilities
                                   ELSE COALESCE(reported_capabilities, '{}'::jsonb) || CAST(:caps AS jsonb) END
        WHERE id=:id'''), {'beat': json.dumps(beat), 'caps': json.dumps(capabilities) if capabilities else None, 'id': link['id']})
    if capabilities and capabilities != {k: v for k, v in (link.get('reported_capabilities') or {}).items() if k in capabilities}:
        event(link, 'in', 'device.capabilities.reported', {'controlCapabilities': capabilities})
    runtime = active_runtime(link['id'])
    if runtime is not None:
        # Same liveness signal the PC kiosk gives: gates extension grants.
        from app.services.session_extensions import lock_row, seen
        seen(lock_row(runtime.id, link_id=link['id']))
    if not was_online:
        event(link, 'in', 'device.online', beat)
    db.session.commit()
    from app.services.session_extensions import dispatch
    dispatch()
    if not was_online:
        notify_vendor(link, 'online')
    fresh = link_by_id(link['id'])
    return dict(device_state(fresh), ok=True)


def record_disconnect(identity):
    try:
        if not ready() or not identity or identity.get('kind') != 'kiosk':
            return
        link = link_by_id(identity['id'])
        if not link or link['device_type'] != CONSOLE_TV:
            return
        event(link, 'system', 'device.socket_disconnected', {})
        db.session.commit()
        notify_vendor(link, 'disconnected')
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Console TV disconnect bookkeeping failed')


# ---------------------------------------------------------------- admin API

def vendor_tv_link(vendor_id, link_id):
    require_ready()
    link = _link("s.id=:id AND s.vendor_id=:vid AND s.status='active'", {'id': positive_id(link_id), 'vid': positive_id(vendor_id)})
    if not link:
        raise KioskError('device_not_found', 404)
    if link['device_type'] != CONSOLE_TV:
        raise KioskError('console_tv_required', 409)
    return link


def stations(vendor_id):
    require_ready()
    vendor_id = positive_id(vendor_id)
    now = utcnow()
    consoles = db.session.execute(text('''SELECT id, console_number, model_number, console_type, configured_input_id
        FROM consoles WHERE vendor_id=:vid ORDER BY console_number, id'''), {'vid': vendor_id}).mappings().all()
    links = {}
    for link_id in db.session.execute(text("SELECT id FROM console_link_sessions WHERE vendor_id=:vid AND status='active'"),
                                      {'vid': vendor_id}).scalars().all():
        link = link_by_id(link_id)
        if link:
            links[link['console_id']] = link
    RuntimeSession = runtime_model()
    running = {r.console_id: r for r in RuntimeSession.query.filter_by(vendor_id=vendor_id, ended_at=None).all()}
    items = []
    for console in consoles:
        console = dict(console)
        link = links.get(console['id'])
        item = dict(station_view(console), linked=bool(link), deviceKind=None, device=None, session=None, display=None)
        runtime = running.get(console['id'])
        if link:
            item['deviceKind'] = link['device_type']
            if link['device_type'] == CONSOLE_TV:
                runtime = runtime or current_runtime(link['id'], now)
                item['device'] = device_view(link, now)
                item['display'] = display_state(link, runtime, now)
        item['session'] = session_contract(runtime, now)
        items.append(item)
    db.session.rollback()
    return {'serverTime': iso(now), 'stations': items, 'tvPlatforms': list(TV_PLATFORMS),
            'offlineAfterSeconds': offline_after()}


def admin_command(vendor_id, link_id, body, actor):
    link = vendor_tv_link(vendor_id, link_id)
    kind = (body or {}).get('commandType') if isinstance(body, dict) else None
    if kind not in COMMAND_TYPES:
        raise KioskError('invalid_command_type', 400)
    runtime = current_runtime(link['id'])
    if kind == 'UNLOCK' and lifecycle(runtime) not in ('ACTIVE', 'EXPIRING'):
        # Only a genuinely authorized session may return the TV to the console.
        raise KioskError('session_not_authorized', 409)
    # HDMI_TEST is allowed on an idle station: the TV switches, reports, then
    # returns to the lock screen on its own (documented in the TV contract).
    command = issue_command(link, kind, runtime=runtime, reason='admin_' + kind.lower(), actor=actor)
    cafe_audit(link['vendor_id'], actor, 'console_tv.command', {'deviceId': link['id'], 'commandId': command['commandId'], 'commandType': kind})
    event(link, 'admin', 'device.command.requested', {'commandId': command['commandId'], 'commandType': kind}, runtime=runtime, actor=actor)
    db.session.commit()
    publish([(link, [(command['type'], command)])])
    return command


def confirm_command(vendor_id, link_id, command_id, body, actor):
    """Staff watched the TV during an HDMI test (or lock) and records what
    actually happened. This is the only path to a verified capability."""
    link = vendor_tv_link(vendor_id, link_id)
    observed = (body or {}).get('observed') if isinstance(body, dict) else None
    if type(observed) is not bool:
        raise KioskError('observed_must_be_boolean', 400)
    try:
        command_id = str(uuid.UUID(str(command_id)))
    except ValueError:
        raise KioskError('invalid_command_id', 400)
    cmd = db.session.execute(text('SELECT * FROM device_commands WHERE id=:id AND link_id=:lid FOR UPDATE'),
                             {'id': command_id, 'lid': link['id']}).mappings().first()
    if not cmd:
        raise KioskError('command_not_found', 404)
    if cmd['command_status'] not in RESULT_STATUSES:
        raise KioskError('command_has_no_result', 409)
    db.session.execute(text('''UPDATE device_commands SET staff_verification=:v, staff_verified_by=:by,
        staff_verified_at=CURRENT_TIMESTAMP WHERE id=:id'''), {'v': 'CONFIRMED' if observed else 'REJECTED', 'by': actor['id'], 'id': command_id})
    _verify_capability(link, cmd['command_type'], cmd['command_status'], staff=observed, actor=actor)
    event(link, 'admin', 'device.capability.staff_verified', {'commandId': command_id, 'observed': observed}, actor=actor)
    cafe_audit(link['vendor_id'], actor, 'console_tv.capability_verified', {'deviceId': link['id'], 'commandId': command_id, 'observed': observed})
    db.session.commit()
    notify_vendor(link, 'verified')
    return {'commandId': command_id, 'staffVerification': 'CONFIRMED' if observed else 'REJECTED',
            'capabilityVerification': link_by_id(link['id'])['capability_verification']}


def _busy(link):
    if active_runtime(link['id']):
        return True
    has_qr = db.session.execute(text("SELECT to_regclass('cafe_play_sessions')")).scalar()
    return bool(has_qr and db.session.execute(text("""SELECT 1 FROM cafe_play_sessions WHERE link_id=:lid
        AND state IN ('reserved','active') LIMIT 1"""), {'lid': link['id']}).scalar())


def revoke(vendor_id, link_id, actor):
    from app.services.kiosk_security import vendor_lock
    vendor_lock(positive_id(vendor_id))
    link = vendor_tv_link(vendor_id, link_id)
    db.session.execute(text('SELECT id FROM console_link_sessions WHERE id=:id FOR UPDATE'), {'id': link['id']})
    if _busy(link):
        # Revoking a link ends its running session in the shared engine; staff end it first.
        raise KioskError('end_session_first', 409)
    db.session.execute(text("""UPDATE console_link_sessions SET status='closed', ended_at=CURRENT_TIMESTAMP, close_reason='revoked'
        WHERE id=:id AND status='active'"""), {'id': link['id']})
    db.session.execute(text("""UPDATE device_commands SET command_status='SUPERSEDED', completed_at=CURRENT_TIMESTAMP
        WHERE link_id=:id AND command_status='PENDING'"""), {'id': link['id']})
    event(link, 'admin', 'device.revoked', {}, actor=actor)
    cafe_audit(link['vendor_id'], actor, 'console_tv.revoked', {'deviceId': link['id'], 'stationId': link['console_id']})
    db.session.commit()
    send_to_device(link, 'device.revoked', envelope('device.revoked', link))
    try:
        from app.services.websocket_service import socketio
        socketio.close_room(f"device_{link['id']}")
    except Exception:
        pass
    notify_vendor(link, 'revoked')
    return {'deviceId': link['id'], 'status': 'revoked'}


def reassign(vendor_id, link_id, body, actor):
    from app.services.kiosk_security import vendor_lock
    vendor_id = positive_id(vendor_id)
    vendor_lock(vendor_id)
    link = vendor_tv_link(vendor_id, link_id)
    target = positive_id((body or {}).get('consoleId') if isinstance(body, dict) else None)
    if target == link['console_id']:
        raise KioskError('same_station', 409)
    if _busy(link):
        raise KioskError('end_session_first', 409)
    _station_for_pairing(vendor_id, target)
    RuntimeSession = runtime_model()
    if RuntimeSession.query.filter_by(console_id=target, ended_at=None).first():
        raise KioskError('station_busy', 409)
    hdmi = normalize_input(body['hdmiInput']) if body.get('hdmiInput') is not None else None
    db.session.execute(text('UPDATE console_link_sessions SET console_id=:cid WHERE id=:id'), {'cid': target, 'id': link['id']})
    db.session.execute(text("""UPDATE device_commands SET command_status='SUPERSEDED', completed_at=CURRENT_TIMESTAMP
        WHERE link_id=:id AND command_status='PENDING'"""), {'id': link['id']})
    if hdmi:
        db.session.execute(text('UPDATE consoles SET configured_input_id=:input WHERE id=:cid'), {'input': hdmi, 'cid': target})
    details = {'deviceId': link['id'], 'fromStationId': link['console_id'], 'toStationId': target}
    event(link, 'admin', 'device.reassigned', details, actor=actor)
    cafe_audit(vendor_id, actor, 'console_tv.reassigned', details)
    db.session.commit()
    fresh = link_by_id(link['id'])
    send_to_device(fresh, 'device.reassigned', envelope('device.reassigned', fresh, station=station_view(fresh)))
    notify_vendor(link, 'reassigned')
    notify_vendor(fresh, 'reassigned')
    return {'deviceId': fresh['id'], 'station': station_view(fresh)}


def set_station_input(vendor_id, console_id, body, actor):
    require_ready()
    vendor_id, console_id = positive_id(vendor_id), positive_id(console_id)
    console = db.session.execute(text('SELECT id, console_type FROM consoles WHERE id=:cid AND vendor_id=:vid FOR UPDATE'),
                                 {'cid': console_id, 'vid': vendor_id}).mappings().first()
    if not console:
        raise KioskError('console_mismatch', 403)
    if station_type(console['console_type']) == 'PC':
        raise KioskError('station_is_pc', 409)
    raw = (body or {}).get('hdmiInput') if isinstance(body, dict) else None
    hdmi = None if raw is None else normalize_input(raw)
    db.session.execute(text('UPDATE consoles SET configured_input_id=:input WHERE id=:cid'), {'input': hdmi, 'cid': console_id})
    event(None, 'admin', 'station.input_configured', {'hdmiInput': hdmi}, actor=actor, vendor_id=vendor_id, console_id=console_id)
    cafe_audit(vendor_id, actor, 'console_tv.input_configured', {'stationId': console_id, 'hdmiInput': hdmi})
    db.session.commit()
    link_id = db.session.execute(text("""SELECT id FROM console_link_sessions WHERE console_id=:cid AND status='active'
        AND device_type='CONSOLE_TV' LIMIT 1"""), {'cid': console_id}).scalar()
    if link_id:
        link = link_by_id(link_id)
        send_to_device(link, 'device.config.updated', envelope('device.config.updated', link, station=station_view(link)))
        notify_vendor(link, 'config')
    return {'stationId': console_id, 'hdmiInput': hdmi}


def device_events(vendor_id, link_id, limit=100):
    require_ready()
    rows = db.session.execute(text('''SELECT id, direction, event_type, payload, actor, runtime_id, session_version, created_at
        FROM device_events WHERE link_id=:lid AND vendor_id=:vid ORDER BY id DESC LIMIT :limit'''),
        {'lid': positive_id(link_id), 'vid': positive_id(vendor_id), 'limit': max(1, min(int(limit), 200))}).mappings().all()
    db.session.rollback()
    return [{'id': r['id'], 'direction': r['direction'], 'type': r['event_type'], 'actor': r['actor'],
             'sessionId': r['runtime_id'], 'sessionVersion': r['session_version'], 'createdAt': iso(r['created_at']),
             'payload': {k: v for k, v in (r['payload'] or {}).items() if k != 'session'}} for r in rows]


def count_pc_links(vendor_id):
    """PC kiosk licences in use; paired TVs do not consume PC seats."""
    return db.session.execute(text("""SELECT count(*) FROM console_link_sessions WHERE vendor_id=:vid AND status='active'
        AND device_type='PC_KIOSK'"""), {'vid': vendor_id}).scalar()
