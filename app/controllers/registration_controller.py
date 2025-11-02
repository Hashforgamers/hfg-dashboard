# app/controllers/registration_controller.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app.extension.extensions import db
from app.models.event import Event
from app.models.registration import Registration

bp_regs = Blueprint('registrations', __name__, url_prefix='/api/vendor/events/<uuid:event_id>/registrations')

def _vendor_id():
    vendor = get_jwt().get("vendor") or {}
    return int(vendor.get("id"))

@bp_regs.get('/')
@jwt_required()
def list_registrations(event_id):
    vid = _vendor_id()
    Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()
    regs = (Registration.query
            .filter_by(event_id=event_id)
            .order_by(Registration.created_at.desc())
            .all())
    return jsonify([{
        "id": str(r.id),
        "team_id": str(r.team_id),
        "status": r.status,
        "payment_status": r.payment_status,
        "created_at": r.created_at.isoformat()
    } for r in regs]), 200

@bp_regs.patch('/<uuid:registration_id>/payment')
@jwt_required()
def update_payment_status(event_id, registration_id):
    vid = _vendor_id()
    Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()
    payload = request.get_json() or {}
    status = payload.get("payment_status")
    if status not in {"pending", "paid", "failed"}:
        return jsonify({"error": "Invalid payment_status"}), 400
    reg = Registration.query.filter_by(id=registration_id, event_id=event_id).first_or_404()
    reg.payment_status = status
    db.session.commit()
    return jsonify({"ok": True}), 200
