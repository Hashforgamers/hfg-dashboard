from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app.services.link_service import list_vendor_pcs, create_link, close_link, count_active_links
from app.services.subscription_service import get_vendor_pc_limit
from app.models.console_link_session import ConsoleLinkSession

bp_vendor_pc = Blueprint('vendor_pc', __name__, url_prefix='/api/vendors/<int:vendor_id>/pcs')

def _auth_vendor(vendor_id):
    # optional: check JWT claim vendor_id == path vendor_id
    return True

@bp_vendor_pc.get('/')
def get_pcs(vendor_id):
    _auth_vendor(vendor_id)
    pcs = list_vendor_pcs(vendor_id)
    limit = get_vendor_pc_limit(vendor_id)
    active = count_active_links(vendor_id)
    return jsonify({
        "plan_limit": limit,
        "active_links": active,
        "remaining_capacity": max(0, limit - active),
        "pcs": [{
            "id": c.id, "number": c.console_number, "brand": c.brand, "model": c.model_number,
            "linked": ConsoleLinkSession.query.filter_by(console_id=c.id, status='active').first() is not None
        } for c in pcs]
    }), 200

@bp_vendor_pc.post('/link')
def link_pc(vendor_id):
    _auth_vendor(vendor_id)
    data = request.get_json()
    sess, err = create_link(vendor_id, data['console_id'], kiosk_id=data.get('kiosk_id'))
    if err:
        return jsonify({"error": err}), 409
    return jsonify({"session_token": sess.session_token, "ws_url": f"wss://your-host/ws?token={sess.session_token}"}), 201

@bp_vendor_pc.post('/unlink')
def unlink_pc(vendor_id):
    _auth_vendor(vendor_id)
    data = request.get_json()
    closed = close_link(session_id=data.get('session_id'), console_id=data.get('console_id'), vendor_id=vendor_id, reason="manual")
    return jsonify({"closed": closed}), 200
