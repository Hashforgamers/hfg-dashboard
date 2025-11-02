from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import func
from app.extension.extensions import db, socketio
from app.models.event import Event
from app.models.team import Team
from app.models.teamMember import TeamMember
from app.models.registration import Registration
from datetime import datetime, timezone

bp_regs = Blueprint('registrations', __name__, url_prefix='/api/vendor/events/<uuid:event_id>/registrations')

def _vendor_id():
    sub = get_jwt().get("sub") or {}
    return int(sub.get("id"))

def _rooms(vendor_id, event_id):
    return f"vendor_{vendor_id}", f"event_{event_id}"

@bp_regs.post('/')
@jwt_required()
def register_team(event_id):
    vid = _vendor_id()
    ev = Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()

    payload = request.get_json() or {}
    team_id = payload.get("team_id")
    contact_name = payload.get("contact_name")
    contact_phone = payload.get("contact_phone")
    contact_email = payload.get("contact_email")

    if not team_id:
        return jsonify({"error": "team_id is required"}), 400

    # deadline check
    now = datetime.now(timezone.utc)
    if ev.registration_deadline and now > ev.registration_deadline:
        return jsonify({"error": "Registration deadline passed"}), 400

    # capacity checks
    team = Team.query.filter_by(id=team_id, event_id=ev.id).first_or_404()
    team_count = db.session.query(func.count(Registration.id)).filter(Registration.event_id == ev.id).scalar()
    if ev.capacity_team and team_count >= ev.capacity_team:
        return jsonify({"error": "Team capacity reached"}), 409

    player_count = db.session.query(func.count(TeamMember.user_id)).join(Team, Team.id == TeamMember.team_id).filter(Team.event_id == ev.id).scalar()
    if ev.capacity_player and player_count >= ev.capacity_player:
        return jsonify({"error": "Player capacity reached"}), 409

    reg = Registration(
        event_id=ev.id,
        team_id=team.id,
        contact_name=contact_name,
        contact_phone=contact_phone,
        contact_email=contact_email,
        waiver_signed=bool(payload.get("waiver_signed", False)),
        payment_status=payload.get("payment_status", "pending"),
        status="confirmed" if ev.registration_fee == 0 else "pending"
    )
    db.session.add(reg)
    db.session.commit()

    r_vendor, r_event = _rooms(vid, ev.id)
    socketio.emit("registration_completed", {"event_id": str(ev.id), "team_id": str(team.id), "registration_id": str(reg.id)}, room=r_vendor)
    socketio.emit("registration_completed", {"event_id": str(ev.id), "team_id": str(team.id), "registration_id": str(reg.id)}, room=r_event)

    return jsonify({"id": str(reg.id), "status": reg.status, "payment_status": reg.payment_status}), 201

@bp_regs.get('/')
@jwt_required()
def list_registrations(event_id):
    vid = _vendor_id()
    ev = Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()

    regs = (Registration.query
            .filter_by(event_id=ev.id)
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
    ev = Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()

    payload = request.get_json() or {}
    status = payload.get("payment_status")
    if status not in {"pending", "paid", "failed"}:
        return jsonify({"error": "Invalid payment_status"}), 400

    reg = Registration.query.filter_by(id=registration_id, event_id=ev.id).first_or_404()
    reg.payment_status = status
    db.session.commit()

    r_vendor, r_event = _rooms(vid, ev.id)
    socketio.emit("registration_payment_updated", {
        "event_id": str(ev.id), "registration_id": str(reg.id), "payment_status": status
    }, room=r_vendor)
    socketio.emit("registration_payment_updated", {
        "event_id": str(ev.id), "registration_id": str(reg.id), "payment_status": status
    }, room=r_event)

    return jsonify({"ok": True}), 200
