# app/controllers/registration_controller.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app.extension.extensions import db
from app.models.event import Event
from app.models.registration import Registration
from app.models.team import Team
from app.services.websocket_service import socketio

bp_regs = Blueprint('registrations', __name__, url_prefix='/api/vendor/events/<uuid:event_id>/registrations')

def _vendor_id():
    vendor = get_jwt().get("vendor") or {}
    return int(vendor.get("id"))

@bp_regs.get('/')
@jwt_required()
def list_registrations(event_id):
    vid = _vendor_id()
    Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()
    rows = (
        db.session.query(Registration, Team.team_name)
        .join(Team, Team.id == Registration.team_id)
        .filter(Registration.event_id == event_id)
        .order_by(Registration.created_at.desc())
        .all()
    )
    return jsonify([{
        "id": str(r.id),
        "event_id": str(r.event_id),
        "team_id": str(r.team_id),
        "team_name": team_name,
        "contact_name": r.contact_name,
        "contact_phone": r.contact_phone,
        "contact_email": r.contact_email,
        "waiver_signed": bool(r.waiver_signed),
        "payment_status": r.payment_status,
        "status": r.status,
        "notes": r.notes,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r, team_name in rows]), 200

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
    try:
        socketio.emit("tournaments_updated", {"vendor_id": vid}, room=f"vendor_{vid}")
    except Exception:
        pass
    return jsonify({"ok": True}), 200
