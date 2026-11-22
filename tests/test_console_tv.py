"""Console Lock TV on the shared kiosk engine, against real PostgreSQL.

Set CAFE_TEST_DATABASE_URL to a disposable PostgreSQL database. Reuses the
cafe wallet integration environment (real session engine, wallet, slot
capacity and outbox code); nothing about money or sessions is mocked. Only
Socket.IO is a recording Mock.
"""
import importlib.util
import os
import sys
import types
from datetime import datetime, timedelta

import jwt
import pytest
from flask import jsonify
from sqlalchemy import text

from test_cafe_wallet import ROOT, env as cafe_env, fund  # noqa: F401  (fixture reuse)

pytestmark = pytest.mark.skipif(not os.getenv('CAFE_TEST_DATABASE_URL', '').startswith('postgresql'),
                                reason='Console TV tables need PostgreSQL (set CAFE_TEST_DATABASE_URL)')


def _load(monkeypatch, name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tv(cafe_env, monkeypatch):
    e = cafe_env
    entitlements = types.ModuleType('app.services.subscription_entitlements')
    entitlements.require_feature = lambda vendor_id, feature: None
    monkeypatch.setitem(sys.modules, entitlements.__name__, entitlements)
    e.tv = _load(monkeypatch, 'app.services.console_tv', 'app/services/console_tv.py')
    controller = _load(monkeypatch, 'app.controllers.console_tv_controller', 'app/controllers/console_tv_controller.py')
    e.link_service = None
    e.app.register_blueprint(controller.bp_console_tv)
    KioskError = sys.modules['app.services.kiosk_security'].KioskError
    e.KioskError = KioskError
    e.app.register_error_handler(KioskError, lambda exc: (jsonify(status='error', code=exc.error_code), exc.code))
    e.socket = sys.modules['app.services.websocket_service'].socketio
    e.engine = sys.modules['app.services.session_extensions']
    with e.app.app_context():
        e.db.session.execute(text('''
            ALTER TABLE consoles ADD COLUMN IF NOT EXISTS console_type varchar(50) DEFAULT 'pc';
            ALTER TABLE consoles ADD COLUMN IF NOT EXISTS model_number varchar(50);
            ALTER TABLE console_link_sessions ADD COLUMN IF NOT EXISTS kiosk_id varchar(64);
            ALTER TABLE console_link_sessions ADD COLUMN IF NOT EXISTS started_at timestamptz DEFAULT now();
            ALTER TABLE console_link_sessions ADD COLUMN IF NOT EXISTS ended_at timestamptz;
            ALTER TABLE console_link_sessions ADD COLUMN IF NOT EXISTS close_reason varchar(64);
            CREATE TABLE IF NOT EXISTS kiosk_rate_limits(key text PRIMARY KEY, window_start timestamptz NOT NULL, attempts integer NOT NULL);
            INSERT INTO vendors(id) VALUES (3) ON CONFLICT DO NOTHING;
            INSERT INTO consoles(id, vendor_id, console_number, console_type, model_number)
              VALUES (3, 1, 3, 'ps5', 'PS5 Bay'), (4, 2, 1, 'ps5', 'Other cafe PS5'), (5, 1, 5, 'ps4', NULL);
            UPDATE consoles SET console_type='ps5', model_number='Lounge PS5' WHERE id=1;
            UPDATE consoles SET console_type='pc' WHERE id=2;
            SELECT setval(pg_get_serial_sequence('console_link_sessions','id'), 50);
        '''))
        e.db.session.commit()
        raw = e.db.engine.raw_connection()
        try:
            raw.cursor().execute((ROOT / 'sql/20261123_console_tv_devices.sql').read_text()); raw.commit()
            # Second run proves the migration is repeatable.
            raw.cursor().execute((ROOT / 'sql/20261123_console_tv_devices.sql').read_text()); raw.commit()
        finally:
            raw.close()
        # Link 1 (console 1) becomes a paired TV; link 2 stays a PC kiosk.
        e.db.session.execute(text("""UPDATE console_link_sessions SET device_type='CONSOLE_TV',
            reported_capabilities='{"switchToHdmi": true, "lockEnforcement": true}' WHERE id=1"""))
        e.db.session.commit()
    e.client = e.app.test_client()
    return e


def vendor_token(e, vendor_id=1):
    now = datetime.utcnow()
    return jwt.encode({'sub': {'type': 'vendor', 'id': vendor_id}, 'iat': now, 'exp': now + timedelta(minutes=5)},
                      e.app.config['JWT_SECRET_KEY'], algorithm='HS256')


def auth(token):
    return {'Authorization': 'Bearer ' + token}


def emitted(e, name, room=None):
    return [c.args[1] for c in e.socket.emit.call_args_list
            if c.args and c.args[0] == name and (room is None or c.kwargs.get('room') == room)]


def running_tv_session(e, link_id=1, minutes_left=30):
    """A real self-QR wallet session acknowledged on the station, enrolled in the engine."""
    fund(e, amount=20000)
    link = e.db.session.get(e.Link, link_id)
    qr = e.s.reserve(1, 1, link, 60, f'tv-base-{link_id}')
    e.db.session.commit()
    e.s.acknowledge(qr.id, e.db.session.get(e.Link, link_id), qr.command_token, True)
    e.db.session.commit()
    row = e.engine.attach(e.db.session.get(e.Link, link_id), {'kind': 'self_qr', 'id': qr.id})
    e.db.session.commit()
    row.reserved_until = datetime.utcnow() + timedelta(minutes=minutes_left)
    e.db.session.commit()
    return row, qr


def commands(e, link_id=1):
    return e.db.session.execute(text('SELECT command_type, command_status, reason, runtime_id FROM device_commands WHERE link_id=:l ORDER BY issued_at'),
                                {'l': link_id}).mappings().all()


# ----------------------------------------------------------------- pairing

def test_pairing_is_admin_approved_single_use_and_cafe_scoped(tv):
    e = tv
    body = {'deviceType': 'CONSOLE_TV', 'tvPlatform': 'ANDROID_TV', 'tvManufacturer': 'Sony', 'tvModel': 'Example',
            'hdmiInput': 'hdmi 1', 'controlCapabilities': {'switchToApp': True, 'switchToHdmi': False, 'lockEnforcement': False}}
    created = e.client.post('/api/kiosk/device/pairing/challenges', json=body)
    assert created.status_code == 201, created.json
    challenge = created.json
    assert len(challenge['pairingCode']) == 9 and challenge['claimSecret']
    claim_url = f"/api/kiosk/device/pairing/challenges/{challenge['challengeId']}/claim"
    # Not approved yet: the TV keeps polling and gets no credential.
    pending = e.client.post(claim_url, json={'claimSecret': challenge['claimSecret']})
    assert pending.status_code == 202 and 'deviceToken' not in pending.json
    assert e.client.post(claim_url, json={'claimSecret': 'guess'}).status_code == 404
    # Another cafe's admin cannot attach the code to our station, and cannot pick their own via the device.
    other = e.client.post('/api/vendors/2/console-devices/pairing/approve', headers=auth(vendor_token(e, 2)),
                          json={'pairingCode': challenge['pairingCode'], 'consoleId': 3})
    assert other.status_code == 403 and other.json['code'] == 'console_mismatch'
    wrong_scope = e.client.post('/api/vendors/1/console-devices/pairing/approve', headers=auth(vendor_token(e, 2)),
                                json={'pairingCode': challenge['pairingCode'], 'consoleId': 3})
    assert wrong_scope.status_code == 403
    pc = e.client.post('/api/vendors/1/console-devices/pairing/approve', headers=auth(vendor_token(e)),
                       json={'pairingCode': challenge['pairingCode'], 'consoleId': 2})
    assert pc.status_code == 409 and pc.json['code'] == 'station_is_pc'
    approved = e.client.post('/api/vendors/1/console-devices/pairing/approve', headers=auth(vendor_token(e)),
                             json={'pairingCode': challenge['pairingCode'].lower(), 'consoleId': 3})
    assert approved.status_code == 200, approved.json
    assert approved.json['station']['hdmiInput'] == 'HDMI_1' and approved.json['station']['consoleType'] == 'PS5'
    # The code is single-use.
    again = e.client.post('/api/vendors/1/console-devices/pairing/approve', headers=auth(vendor_token(e)),
                          json={'pairingCode': challenge['pairingCode'], 'consoleId': 5})
    assert again.status_code == 404
    claimed = e.client.post(claim_url, json={'claimSecret': challenge['claimSecret']})
    assert claimed.status_code == 200, claimed.json
    token = claimed.json['deviceToken']
    assert claimed.json['station']['stationId'] == 3 and claimed.json['vendorId'] == 1
    assert claimed.json['device']['capabilityVerification']['lockEnforcement']['status'] == 'UNSUPPORTED'
    assert claimed.json['device']['capabilityVerification']['switchToApp']['status'] == 'UNVERIFIED'
    assert e.client.post(claim_url, json={'claimSecret': challenge['claimSecret']}).status_code == 410
    state = e.client.get('/api/kiosk/device/state', headers=auth(token))
    assert state.status_code == 200 and state.json['session'] is None and state.json['station']['stationId'] == 3
    # Rotation keeps the device id, kills the old bearer.
    rotated = e.client.post('/api/kiosk/device/credentials/rotate', headers=auth(token)).json
    assert rotated['deviceId'] == claimed.json['deviceId']
    assert e.client.get('/api/kiosk/device/state', headers=auth(token)).status_code == 401
    assert e.client.get('/api/kiosk/device/state', headers=auth(rotated['deviceToken'])).status_code == 200
    # A PC kiosk bearer is not a TV credential.
    assert e.client.get('/api/kiosk/device/state', headers=auth('agent-other')).json['code'] == 'console_tv_token_required'


def test_pairing_codes_expire_and_creation_is_rate_limited(tv):
    e = tv
    body = {'tvPlatform': 'WEBOS'}
    first = e.client.post('/api/kiosk/device/pairing/challenges', json=body).json
    with e.app.app_context():
        e.db.session.execute(text("UPDATE device_pairing_challenges SET expires_at=now()-interval '1 second'"))
        e.db.session.commit()
    late = e.client.post('/api/vendors/1/console-devices/pairing/approve', headers=auth(vendor_token(e)),
                         json={'pairingCode': first['pairingCode'], 'consoleId': 3})
    assert late.status_code == 404
    gone = e.client.post(f"/api/kiosk/device/pairing/challenges/{first['challengeId']}/claim", json={'claimSecret': first['claimSecret']})
    assert gone.status_code == 410 and gone.json['code'] == 'pairing_expired'
    assert e.client.post('/api/kiosk/device/pairing/challenges', json={'tvPlatform': 'ROKU'}).status_code == 400
    statuses = [e.client.post('/api/kiosk/device/pairing/challenges', json=body).status_code for _ in range(10)]
    assert statuses[-1] == 429


# ----------------------------------------------------------------- session engine

def test_session_start_unlocks_and_backend_expiry_locks_without_overtime(tv):
    e = tv
    with e.app.app_context():
        row, qr = running_tv_session(e)
        e.engine.dispatch()
        assert [c['command_type'] for c in commands(e)] == ['UNLOCK']
        started = emitted(e, 'session.started', 'device_1')
        assert started and started[-1]['session']['status'] == 'ACTIVE' and started[-1]['sessionVersion'] == row.revision
        unlock = emitted(e, 'device.unlock.requested', 'device_1')[-1]
        for field in ('commandId', 'deviceId', 'stationId', 'sessionId', 'sessionVersion', 'commandType', 'issuedAt', 'expiresAt'):
            assert unlock[field] is not None
        # PC kiosk rooms never receive the TV contract.
        assert not [c for c in e.socket.emit.call_args_list if str(c.kwargs.get('room', '')).startswith('kiosk_link_') and c.args[0].startswith('device.')]
        result = e.client.post(f"/api/kiosk/device/commands/{unlock['commandId']}/result", headers=auth('agent-secret'),
                               json={'status': 'SUCCEEDED', 'observedInput': 'HDMI_1'})
        assert result.status_code == 200 and result.json['evidence'] == 'device_reported'
        assert result.json['followUpCommands'] == []
        # Authoritative expiry with the TV offline: engine ends at the paid boundary, no metered overtime.
        row = e.db.session.get(e.engine.RuntimeSession, row.id)
        boundary = datetime.utcnow() - timedelta(seconds=40)
        row.reserved_until = boundary; row.last_seen_at = datetime.utcnow() - timedelta(minutes=10)
        e.db.session.commit()
        e.engine.tick()
        row = e.db.session.get(e.engine.RuntimeSession, row.id)
        assert row.ended_at == boundary
        assert not [p for p in e.engine.segments(row) if p.is_overrun]
        assert [c['command_type'] for c in commands(e)] == ['UNLOCK', 'LOCK']
        assert emitted(e, 'session.expired', 'device_1')[-1]['session']['status'] == 'EXPIRED'
        e.engine.dispatch()  # replay of dispatch cannot issue a second lock for the same session end
        assert len(commands(e)) == 2
        state = e.client.get('/api/kiosk/device/state', headers=auth('agent-secret')).json
        assert state['session']['status'] == 'EXPIRED' and state['session']['playAllowed'] is False
        assert state['display']['security'] == 'NOT_SECURE' and state['display']['controlStatus'] == 'PENDING'
        lock = state['pendingCommands'][0]
        e.client.post(f"/api/kiosk/device/commands/{lock['commandId']}/result", headers=auth('agent-secret'),
                      json={'status': 'RECEIVED'})
        assert e.client.get('/api/kiosk/device/state', headers=auth('agent-secret')).json['display']['controlStatus'] == 'PENDING'
        e.client.post(f"/api/kiosk/device/commands/{lock['commandId']}/result", headers=auth('agent-secret'),
                      json={'status': 'SUCCEEDED', 'lockScreenVisible': True})
        listing = e.client.get('/api/vendors/1/console-devices', headers=auth(vendor_token(e))).json
        station = next(s for s in listing['stations'] if s['stationId'] == 1)
        assert station['display']['security'] == 'SECURE' and station['display']['lastSuccessfulLock']
        assert station['device']['capabilityVerification']['lockEnforcement']['status'] == 'DEVICE_REPORTED_SUCCESS'


def test_pc_kiosk_session_keeps_existing_overtime_and_gets_no_tv_traffic(tv):
    e = tv
    with e.app.app_context():
        row, qr = running_tv_session(e, link_id=2)
        e.engine.dispatch()
        row = e.db.session.get(e.engine.RuntimeSession, row.id)
        row.reserved_until = datetime.utcnow() - timedelta(seconds=40); e.db.session.commit()
        e.engine.tick()
        row = e.db.session.get(e.engine.RuntimeSession, row.id)
        assert row.ended_at is None and row.status == 'overtime_pending'  # unchanged PC rule
        assert commands(e, 2) == []
        assert e.db.session.execute(text('SELECT count(*) FROM device_events WHERE link_id=2')).scalar() == 0
        assert emitted(e, 'session.updated', 'kiosk_link_2')  # legacy PC event still delivered
        assert not [c for c in e.socket.emit.call_args_list if c.kwargs.get('room') == 'device_2']
        assert e.tv.count_pc_links(1) == 1  # the TV on link 1 does not take a PC seat
        pc = e.client.get('/api/kiosk/session', headers=auth('agent-other')).json
        assert 'timer' not in pc and 'console_tv_v1' not in pc['capabilities']


def test_stale_superseded_and_expired_results_cannot_reopen_a_station(tv):
    e = tv
    with e.app.app_context():
        row, qr = running_tv_session(e)
        e.engine.dispatch()
        unlock = emitted(e, 'device.unlock.requested', 'device_1')[-1]
        e.engine.stop(e.engine.lock_row(row.id), {'mode': 'now', 'idempotency_key': 'tv-stop-now-1'})
        e.db.session.commit(); e.engine.dispatch()
        # The end superseded the pending UNLOCK; its late result is rejected.
        late = e.client.post(f"/api/kiosk/device/commands/{unlock['commandId']}/result", headers=auth('agent-secret'), json={'status': 'SUCCEEDED'})
        assert late.status_code == 409 and late.json['code'] == 'stale_command'
        assert emitted(e, 'session.ended', 'device_1')
        lock = [c for c in commands(e) if c['command_type'] == 'LOCK']
        assert len(lock) == 1 and lock[0]['command_status'] == 'PENDING'
        # Admin unlock is refused without a genuinely authorized session.
        refused = e.client.post('/api/vendors/1/console-devices/1/commands', headers=auth(vendor_token(e)), json={'commandType': 'UNLOCK'})
        assert refused.status_code == 409 and refused.json['code'] == 'session_not_authorized'
        # An expired command cannot be completed afterwards.
        e.db.session.execute(text("UPDATE device_commands SET expires_at=now()-interval '1 second' WHERE command_type='LOCK'")); e.db.session.commit()
        pending = e.client.get('/api/kiosk/device/commands', headers=auth('agent-secret')).json['commands']
        assert pending == []
        lock_id = e.db.session.execute(text("SELECT id FROM device_commands WHERE command_type='LOCK'")).scalar()
        expired = e.client.post(f'/api/kiosk/device/commands/{lock_id}/result', headers=auth('agent-secret'), json={'status': 'SUCCEEDED'})
        assert expired.status_code == 409 and expired.json['code'] == 'command_expired'
        state = e.client.get('/api/kiosk/device/state', headers=auth('agent-secret')).json
        assert state['display']['controlStatus'] == 'FAILED' and state['display']['security'] == 'NOT_SECURE'


def test_late_unlock_success_after_end_triggers_relock(tv):
    e = tv
    with e.app.app_context():
        row, qr = running_tv_session(e)
        e.engine.dispatch()
        unlock = emitted(e, 'device.unlock.requested', 'device_1')[-1]
        # Session ends in the engine without going through dispatch yet (no LOCK issued).
        e.engine.finish(e.engine.lock_row(row.id)); e.db.session.commit()
        response = e.client.post(f"/api/kiosk/device/commands/{unlock['commandId']}/result", headers=auth('agent-secret'), json={'status': 'SUCCEEDED'})
        assert response.status_code == 200
        follow = response.json['followUpCommands']
        assert follow and follow[0]['commandType'] == 'LOCK' and follow[0]['reason'] == 'stale_unlock'
        # Same result again is idempotent; a conflicting one is rejected.
        assert e.client.post(f"/api/kiosk/device/commands/{unlock['commandId']}/result", headers=auth('agent-secret'), json={'status': 'SUCCEEDED'}).json['duplicate']
        assert e.client.post(f"/api/kiosk/device/commands/{unlock['commandId']}/result", headers=auth('agent-secret'), json={'status': 'FAILED'}).status_code == 409


def test_heartbeat_marks_online_and_keeps_shared_liveness(tv):
    e = tv
    with e.app.app_context():
        row, qr = running_tv_session(e)
        row = e.db.session.get(e.engine.RuntimeSession, row.id)
        row.last_seen_at = datetime.utcnow() - timedelta(minutes=5); e.db.session.commit()
        before = e.client.get('/api/vendors/1/console-devices', headers=auth(vendor_token(e))).json
        assert next(s for s in before['stations'] if s['stationId'] == 1)['device']['online'] is False
        beat = e.client.post('/api/kiosk/device/heartbeat', headers=auth('agent-secret'),
                             json={'appVersion': '1.0.0', 'currentInput': 'HASH_APP', 'lockScreenVisible': False,
                                   'controlCapabilities': {'switchToApp': True}})
        assert beat.status_code == 200 and beat.json['session']['status'] == 'ACTIVE'
        assert beat.json['session']['expiresAt'] and beat.json['session']['serverTime']
        row = e.db.session.get(e.engine.RuntimeSession, row.id)
        e.db.session.refresh(row)
        assert row.last_seen_at > datetime.utcnow() - timedelta(seconds=30)
        after = e.client.get('/api/vendors/1/console-devices', headers=auth(vendor_token(e))).json
        station = next(s for s in after['stations'] if s['stationId'] == 1)
        assert station['device']['online'] and station['device']['controlCapabilities']['switchToApp'] is True
        assert station['session']['status'] == 'ACTIVE' and station['consoleType'] == 'PS5'
        assert e.client.post('/api/kiosk/device/heartbeat', headers=auth('agent-secret'), json={'uptimeSeconds': -1}).status_code == 400


def test_admin_controls_are_cafe_scoped_and_revoke_needs_an_ended_session(tv):
    e = tv
    with e.app.app_context():
        assert e.client.get('/api/vendors/1/console-devices', headers=auth(vendor_token(e, 2))).status_code == 403
        assert e.client.post('/api/vendors/2/console-devices/1/commands', headers=auth(vendor_token(e, 2)),
                             json={'commandType': 'LOCK'}).status_code == 404
        test = e.client.post('/api/vendors/1/console-devices/1/commands', headers=auth(vendor_token(e)), json={'commandType': 'HDMI_TEST'})
        assert test.status_code == 202 and test.json['hdmiInput'] is None
        e.client.post(f"/api/kiosk/device/commands/{test.json['commandId']}/result", headers=auth('agent-secret'), json={'status': 'UNVERIFIED'})
        verified = e.client.post(f"/api/vendors/1/console-devices/1/commands/{test.json['commandId']}/verify",
                                 headers=auth(vendor_token(e)), json={'observed': True})
        assert verified.json['capabilityVerification']['switchToHdmi']['status'] == 'STAFF_CONFIRMED'
        # PC link 2's bearer cannot report on the TV's command.
        assert e.client.post(f"/api/kiosk/device/commands/{test.json['commandId']}/result", headers=auth('agent-other'),
                             json={'status': 'SUCCEEDED'}).status_code == 403
        config = e.client.put('/api/vendors/1/console-devices/stations/1/display', headers=auth(vendor_token(e)), json={'hdmiInput': 'HDMI_2'})
        assert config.json['hdmiInput'] == 'HDMI_2'
        row, qr = running_tv_session(e)
        busy = e.client.post('/api/vendors/1/console-devices/1/revoke', headers=auth(vendor_token(e)))
        assert busy.status_code == 409 and busy.json['code'] == 'end_session_first'
        moved = e.client.post('/api/vendors/1/console-devices/1/reassign', headers=auth(vendor_token(e)), json={'consoleId': 5})
        assert moved.status_code == 409
        e.engine.finish(e.engine.lock_row(row.id)); e.db.session.commit()
        qr = e.db.session.get(e.m.CafePlaySession, qr.id)
        assert qr.state == 'completed'
        moved = e.client.post('/api/vendors/1/console-devices/1/reassign', headers=auth(vendor_token(e)), json={'consoleId': 5})
        assert moved.status_code == 200 and moved.json['station']['consoleType'] == 'PS4'
        assert emitted(e, 'device.reassigned', 'device_1')
        revoked = e.client.post('/api/vendors/1/console-devices/1/revoke', headers=auth(vendor_token(e)))
        assert revoked.status_code == 200
        assert e.client.get('/api/kiosk/device/state', headers=auth('agent-secret')).status_code == 401
        history = e.client.get('/api/vendors/1/console-devices/1/events', headers=auth(vendor_token(e)))
        assert history.status_code == 200 and {'device.revoked', 'device.reassigned'} <= {x['type'] for x in history.json['events']}


def test_existing_kiosk_session_endpoint_adds_timer_contract_only_for_tv(tv):
    e = tv
    with e.app.app_context():
        row, qr = running_tv_session(e)
        result = e.client.get('/api/kiosk/session', headers=auth('agent-secret')).json
        assert result['session']['runtime_id'] == row.id  # existing snapshot, unchanged shape
        assert 'console_tv_v1' in result['capabilities'] and 'session_extensions_v1' in result['capabilities']
        timer = result['timer']
        assert timer['sessionId'] == row.id and timer['status'] == 'ACTIVE' and timer['version'] == row.revision
        assert set(['startedAt', 'expiresAt', 'serverTime']) <= set(timer)


def test_socket_rooms_keep_pc_and_tv_contracts_apart(tv, monkeypatch):
    import ast
    import threading
    from types import SimpleNamespace
    from unittest.mock import Mock
    from flask import g, session
    from flask_socketio import SocketIO, disconnect, emit, join_room, leave_room
    e = tv
    socket = SocketIO(e.app, async_mode='threading')
    monkeypatch.setattr(sys.modules['app.services.websocket_service'], 'socketio', socket)
    security = sys.modules['app.services.kiosk_security']
    tree = ast.parse((ROOT / 'app/services/websocket_service.py').read_text())
    names = ('register_dashboard_events', '_socket_identity', '_emit_to_kiosk', '_console_tv_call')
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    scope = dict(socketio=socket, session=session, g=g, db=e.db, text=text, join_room=join_room, leave_room=leave_room,
                 emit=emit, disconnect=disconnect, linked_identity=security.linked_identity,
                 vendor_identity=security.vendor_identity, KioskError=security.KioskError, Dict=dict, Any=object,
                 _log_info=Mock(), _log_err=Mock(), _log_warn=Mock(), _lock=threading.Lock(), _joined_vendor_ids=set(),
                 _upstream_sio=SimpleNamespace(connected=False))
    exec(compile(tree, '<socket handlers>', 'exec'), scope)
    scope['register_dashboard_events']()
    with e.app.app_context():
        tv_client = socket.test_client(e.app, auth={'session_token': 'agent-secret'})
        pc_client = socket.test_client(e.app, auth={'session_token': 'agent-other', 'console_id': 2})
        assert tv_client.is_connected() and pc_client.is_connected()
        scope['_emit_to_kiosk'](2, 'unlock_request', {'console_id': 2})
        assert [m['name'] for m in pc_client.get_received()] == ['unlock_request']
        assert tv_client.get_received() == []
        e.tv.send_to_device(e.tv.link_by_id(1), 'device.config.updated', {'v': 1})
        assert [m['name'] for m in tv_client.get_received()] == ['device.config.updated']
        assert pc_client.get_received() == []
        ack = tv_client.emit('device.heartbeat', {'appVersion': '1.0.0'}, callback=True)
        assert ack['ok'] is True and ack['device']['online'] is True
        denied = pc_client.emit('device.heartbeat', {}, callback=True)
        assert denied == {'ok': False, 'code': 'console_tv_token_required'}
        tv_client.disconnect()
        assert e.db.session.execute(text("SELECT count(*) FROM device_events WHERE link_id=1 AND event_type='device.socket_disconnected'")).scalar() == 1
        pc_client.disconnect()
