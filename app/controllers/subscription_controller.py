from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.services.subscription_service import (
    get_active_subscription, change_subscription, provision_default_subscription, get_vendor_pc_limit
)

bp_subs = Blueprint('subscriptions', __name__, url_prefix='/vendors/<int:vendor_id>/subscription')

@bp_subs.get('/')
def get_subscription(vendor_id):
    sub = get_active_subscription(vendor_id)
    if not sub:
        return jsonify({"status": "none"}), 200
    return jsonify({
        "status": sub.status.value,
        "package": sub.package.code,
        "pc_limit": sub.package.pc_limit,
        "period_start": sub.current_period_start.isoformat(),
        "period_end": sub.current_period_end.isoformat()
    }), 200

@bp_subs.post('/provision-default')
def provision_default(vendor_id):
    provision_default_subscription(vendor_id)
    return jsonify({"ok": True}), 201

@bp_subs.post('/change')
def change(vendor_id):
    data = request.get_json()
    pkg = data['package_code']       # 'base' | 'pro' | 'custom'
    immediate = data.get('immediate', True)
    unit_amount = data.get('unit_amount', 0)
    res = change_subscription(vendor_id, pkg, immediate=immediate, unit_amount=unit_amount)
    return jsonify({"ok": True, "new_package": res.package.code}), 200

@bp_subs.get('/limit')
def get_limit(vendor_id):
    return jsonify({"pc_limit": get_vendor_pc_limit(vendor_id)}), 200
