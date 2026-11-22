"""Hash Console Lock (Smart TV) routes.

Device routes live next to the PC kiosk ones under /api/kiosk/device/* and use
the same opaque link bearer. Cafe admin routes mirror /api/vendors/<id>/pcs.
Session start/end/extend are NOT duplicated here: TVs use the existing
/api/kiosk/session, /api/kiosk/session/extension/quote, /continue, /stop and
/api/cafe/agent/* endpoints, and staff use the existing dashboard controls.
"""
import jwt
from flask import Blueprint, current_app, jsonify, request

from app.extension.extensions import db
from app.services import console_tv as tv
from app.services.kiosk_security import KioskError, bearer_token, check_scope, vendor_identity

bp_console_tv = Blueprint('console_tv', __name__)


def _body():
    data = request.get_json(silent=True)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise KioskError('invalid_json', 400)
    return data


def _private(response, status=200):
    response = jsonify(response) if not hasattr(response, 'headers') else response
    response.headers['Cache-Control'] = 'private, no-store'
    response.vary.add('Authorization')
    return response, status


def admin(vendor_id, permission):
    """Cafe owner token, or a staff access token holding `permission`, for this cafe only."""
    token = bearer_token()
    identity = vendor_identity(token, permission=permission)
    check_scope(identity, vendor_id)
    claims = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'],
                        options={'verify_sub': False, 'require': ['exp', 'sub']})
    staff = claims.get('staff') or {}
    return {'id': str(staff.get('id') or f"owner-{identity['vendor_id']}")[:64],
            'name': str(staff.get('name') or 'Owner')[:80]}


# ------------------------------------------------------------- device

@bp_console_tv.post('/api/kiosk/device/pairing/challenges')
def create_pairing_challenge():
    return _private(tv.create_challenge(_body()), 201)


@bp_console_tv.post('/api/kiosk/device/pairing/challenges/<challenge_id>/claim')
def claim_pairing_challenge(challenge_id):
    status, result = tv.claim_pairing(challenge_id, _body())
    return _private(result, status)


@bp_console_tv.get('/api/kiosk/device/state')
def device_state():
    return _private(tv.device_state(tv.device_link()))


@bp_console_tv.post('/api/kiosk/device/heartbeat')
def device_heartbeat():
    return _private(tv.heartbeat(tv.device_link(), _body()))


@bp_console_tv.get('/api/kiosk/device/commands')
def device_pending_commands():
    link = tv.device_link()
    commands = tv.pending_commands(link)
    db.session.commit()
    return _private({'commands': commands, 'serverTime': tv.iso(tv.utcnow())})


@bp_console_tv.post('/api/kiosk/device/commands/<command_id>/result')
def device_command_result(command_id):
    link = tv.device_link()
    body = dict(_body(), commandId=command_id)
    result, follow_up = tv.record_result(link, body)
    db.session.commit()
    tv.publish([(link, [(c['type'], c) for c in follow_up])] if follow_up else [])
    tv.notify_vendor(link, 'command_result')
    return _private(dict(result, followUpCommands=follow_up))


@bp_console_tv.post('/api/kiosk/device/credentials/rotate')
def rotate_device_credential():
    return _private(tv.rotate_credential(tv.device_link()))


# ------------------------------------------------------------- cafe admin

@bp_console_tv.get('/api/vendors/<int:vendor_id>/console-devices')
def list_console_devices(vendor_id):
    admin(vendor_id, 'dashboard.view')
    return _private(tv.stations(vendor_id))


@bp_console_tv.post('/api/vendors/<int:vendor_id>/console-devices/pairing/approve')
def approve_console_device(vendor_id):
    actor = admin(vendor_id, 'gaming.manage')
    from app.services.subscription_entitlements import require_feature
    blocked = require_feature(vendor_id, 'kiosk')
    if blocked:
        return blocked
    return _private(tv.approve_pairing(vendor_id, actor, _body()), 200)


@bp_console_tv.get('/api/vendors/<int:vendor_id>/console-devices/<int:device_id>/events')
def console_device_events(vendor_id, device_id):
    admin(vendor_id, 'dashboard.view')
    limit = request.args.get('limit', '100')
    if not limit.isdigit():
        raise KioskError('invalid_limit', 400)
    return _private({'events': tv.device_events(vendor_id, device_id, int(limit))})


@bp_console_tv.post('/api/vendors/<int:vendor_id>/console-devices/<int:device_id>/commands')
def console_device_command(vendor_id, device_id):
    actor = admin(vendor_id, 'gaming.manage')
    return _private(tv.admin_command(vendor_id, device_id, _body(), actor), 202)


@bp_console_tv.post('/api/vendors/<int:vendor_id>/console-devices/<int:device_id>/commands/<command_id>/verify')
def console_device_verify(vendor_id, device_id, command_id):
    actor = admin(vendor_id, 'gaming.manage')
    return _private(tv.confirm_command(vendor_id, device_id, command_id, _body(), actor))


@bp_console_tv.post('/api/vendors/<int:vendor_id>/console-devices/<int:device_id>/revoke')
def revoke_console_device(vendor_id, device_id):
    actor = admin(vendor_id, 'gaming.manage')
    return _private(tv.revoke(vendor_id, device_id, actor))


@bp_console_tv.post('/api/vendors/<int:vendor_id>/console-devices/<int:device_id>/reassign')
def reassign_console_device(vendor_id, device_id):
    actor = admin(vendor_id, 'gaming.manage')
    return _private(tv.reassign(vendor_id, device_id, _body(), actor))


@bp_console_tv.put('/api/vendors/<int:vendor_id>/console-devices/stations/<int:console_id>/display')
def configure_station_display(vendor_id, console_id):
    actor = admin(vendor_id, 'gaming.manage')
    return _private(tv.set_station_input(vendor_id, console_id, _body(), actor))
