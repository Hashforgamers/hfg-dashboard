from flask import Blueprint, jsonify, request
from app.extension.extensions import db
from app.services.kiosk_security import KioskError, runtime_identity, positive_id, check_scope
from app.services.kiosk_runtime import booking_window, expire_vendor

bp_kiosk = Blueprint('kiosk_runtime', __name__)


@bp_kiosk.get('/api/bookings/<int:booking_id>/remaining')
def remaining(booking_id):
    identity = runtime_identity()
    console_id = identity.get('console_id') or positive_id(request.args.get('console_id'))
    check_scope(identity, identity['vendor_id'], console_id)
    expire_vendor(identity['vendor_id'])
    window = booking_window(identity['vendor_id'], booking_id, console_id)
    return jsonify({'status': 'success', 'data': window}), 200


def install_kiosk_errors(app):
    @app.errorhandler(KioskError)
    def kiosk_error(exc):
        db.session.rollback()
        response = jsonify({'status': 'error', 'code': exc.error_code})
        response.status_code = exc.code
        if exc.code == 429:
            response.headers['Retry-After'] = '60'
        return response
