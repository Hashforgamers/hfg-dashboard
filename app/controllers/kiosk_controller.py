from flask import Blueprint, jsonify, request
from app.extension.extensions import db
from app.services.kiosk_security import KioskError, runtime_identity, positive_id, check_scope, rate_limit
from app.services.kiosk_runtime import booking_window, expire_vendor, secure_start

bp_kiosk = Blueprint('kiosk_runtime', __name__)


@bp_kiosk.get('/api/bookings/<int:booking_id>/remaining')
def remaining(booking_id):
    identity = runtime_identity()
    console_id = identity.get('console_id') or positive_id(request.args.get('console_id'))
    check_scope(identity, identity['vendor_id'], console_id)
    expire_vendor(identity['vendor_id'])
    window = booking_window(identity['vendor_id'], booking_id, console_id)
    if identity['kind']=='kiosk' and window.get('runtime'):
        from app.services.session_extensions import lock_row,seen,dispatch
        seen(lock_row(window['runtime']['runtime_id'],link_id=identity['id']))
        db.session.commit();dispatch()
    return jsonify({'status': 'success', 'data': window}), 200


def install_kiosk_errors(app):
    @app.errorhandler(KioskError)
    def kiosk_error(exc):
        db.session.rollback()
        messages={
            'token_required':'PC authentication is required. Send the active PC link token in the Authorization Bearer header.',
            'invalid_session_token':'The PC link token is invalid or inactive. Re-link this kiosk.',
            'token_expired':'The login token expired. Use the active PC link token for kiosk runtime requests.',
            'token_invalid':'The authentication token is invalid.',
            'kiosk_token_required':'This endpoint requires an active PC link token, not a dashboard login token.',
            'access_code_required':'Send the booking access code from the QR ticket or access-code entry.',
            'invalid_access_code':'The booking access code is invalid.',
            'booking_not_accepted':'The cafe has not accepted this booking yet.',
            'booking_console_mismatch':'This booking is assigned to another PC.',
            'session_not_active':'This booking is outside its scheduled play window.',
            'rate_limited':'Too many attempts. Please wait one minute.'}
        response = jsonify({'status': 'error', 'code': exc.error_code,'message':messages.get(exc.error_code,exc.error_code.replace('_',' ').capitalize())})
        response.status_code = exc.code
        if exc.code == 429:
            response.headers['Retry-After'] = '60'
        return response


@bp_kiosk.post('/api/kiosk/owner-pin/validate')
def validate_owner_pin():
    """Authorize a specific native owner action; never end or settle a gaming session."""
    import secrets
    import uuid
    from datetime import datetime,timedelta,timezone
    from flask import current_app
    from sqlalchemy import text
    from werkzeug.security import check_password_hash
    identity=runtime_identity()
    if identity['kind']!='kiosk':raise KioskError('kiosk_token_required',403)
    rate_limit(identity['console_id'])
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise KioskError('invalid_json',400)
    pin=data.get('pin')
    if not isinstance(pin,str) or not pin.isascii() or not pin.isdigit() or not 4<=len(pin)<=6:
        raise KioskError('invalid_pin_format',400)
    action=data.get('action')
    if action not in ('force_exit','admin_settings'):raise KioskError('invalid_action',400)
    row=db.session.execute(text('SELECT p.pin_code,v.owner_name FROM vendor_pins p JOIN vendors v ON v.id=p.vendor_id WHERE p.vendor_id=:vid'),{'vid':identity['vendor_id']}).mappings().first()
    valid=False
    if row:
        stored=str(row['pin_code'])
        valid=secrets.compare_digest(stored.encode(),pin.encode())
        if not valid:
            try:valid=check_password_hash(stored,pin)
            except (ValueError,TypeError):pass
    if not valid:
        current_app.logger.warning('Kiosk owner validation rejected vendor=%s console=%s',identity['vendor_id'],identity['console_id'])
        raise KioskError('invalid_owner_pin',401)
    now=datetime.now(timezone.utc);reference=str(uuid.uuid4())
    current_app.logger.info('Kiosk owner action authorized vendor=%s console=%s action=%s reference=%s',identity['vendor_id'],identity['console_id'],action,reference)
    response=jsonify(status='success',authorized=True,action=action,authorization_id=reference,
        vendor_id=identity['vendor_id'],console_id=identity['console_id'],link_id=identity['id'],
        owner={'id':f"owner-{identity['vendor_id']}",'role':'owner','name':row['owner_name'] or 'Owner'},
        server_time=now.isoformat(),expires_at=(now+timedelta(seconds=60)).isoformat(),expires_in_seconds=60)
    response.headers['Cache-Control']='private, no-store';response.vary.add('Authorization')
    return response,200


@bp_kiosk.post('/api/kiosk/booking/verify')
@secure_start(verify_only=True)
def verify_kiosk_booking():
    # Shared validation returns before this handler; no redemption or unlock here.
    raise KioskError('verification_failed',500)
