from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy.exc import IntegrityError
from app.services.websocket_service import socketio
from app.extension.extensions import db
from app.models.event import Event
from app.models.team import Team
from app.models.teamMember import TeamMember

bp_teams = Blueprint('teams', __name__, url_prefix='/api/vendor/events/<uuid:event_id>/teams')

def _vendor_id():
    sub = get_jwt().get("sub") or {}
    return int(sub.get("id"))

def _rooms(vendor_id, event_id):
    return f"vendor_{vendor_id}", f"event_{event_id}"

@bp_teams.post('/')
@jwt_required()
def create_team(event_id):
    vid = _vendor_id()
    # Ensure event belongs to vendor
    ev = Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()

    payload = request.get_json() or {}
    name = payload.get("name")
    created_by_user = payload.get("created_by_user")
    is_individual = bool(payload.get("is_individual", False))
    if not name or not created_by_user:
        return jsonify({"error": "name and created_by_user are required"}), 400

    team = Team(event_id=ev.id, name=name, created_by_user=created_by_user, is_individual=is_individual)
    db.session.add(team)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Team name already exists for this event"}), 409

    r_vendor, r_event = _rooms(vid, ev.id)
    socketio.emit("team_created", {"event_id": str(ev.id), "team_id": str(team.id), "name": team.name}, room=r_vendor)
    socketio.emit("team_created", {"event_id": str(ev.id), "team_id": str(team.id), "name": team.name}, room=r_event)

    return jsonify({"id": str(team.id), "name": team.name}), 201

@bp_teams.get('/<uuid:team_id>/members')
@jwt_required()
def list_members(event_id, team_id):
    vid = _vendor_id()
    ev = Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()
    members = (TeamMember.query
               .filter_by(team_id=team_id)
               .order_by(TeamMember.joined_at.asc())
               .all())
    return jsonify([{
        "user_id": m.user_id, "role": m.role, "joined_at": m.joined_at.isoformat()
    } for m in members]), 200

@bp_teams.post('/<uuid:team_id>/members')
@jwt_required()
def add_member(event_id, team_id):
    vid = _vendor_id()
    ev = Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()

    payload = request.get_json() or {}
    user_id = payload.get("user_id")
    role = payload.get("role", "member")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    # Enforce team size rules
    team = Team.query.filter_by(id=team_id, event_id=ev.id).first_or_404()
    current_size = TeamMember.query.filter_by(team_id=team_id).count()
    if team.is_individual or ev.max_team_size == 1:
        return jsonify({"error": "This team is individual; cannot add more members"}), 400
    if ev.max_team_size and current_size >= ev.max_team_size:
        return jsonify({"error": f"Max team size {ev.max_team_size} reached"}), 400

    tm = TeamMember(team_id=team_id, user_id=user_id, role=role)
    db.session.add(tm)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Member already in team"}), 409

    r_vendor, r_event = _rooms(vid, ev.id)
    socketio.emit("member_added", {"event_id": str(ev.id), "team_id": str(team_id), "user_id": user_id, "role": role}, room=r_vendor)
    socketio.emit("member_added", {"event_id": str(ev.id), "team_id": str(team_id), "user_id": user_id, "role": role}, room=r_event)
    return jsonify({"ok": True}), 201

@bp_teams.delete('/<uuid:team_id>/members/<int:user_id>')
@jwt_required()
def remove_member(event_id, team_id, user_id):
    vid = _vendor_id()
    ev = Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()
    tm = TeamMember.query.filter_by(team_id=team_id, user_id=user_id).first()
    if not tm:
        return jsonify({"error": "Member not found"}), 404

    db.session.delete(tm)
    db.session.commit()

    r_vendor, r_event = _rooms(vid, ev.id)
    socketio.emit("member_removed", {"event_id": str(ev.id), "team_id": str(team_id), "user_id": user_id}, room=r_vendor)
    socketio.emit("member_removed", {"event_id": str(ev.id), "team_id": str(team_id), "user_id": user_id}, room=r_event)
    return jsonify({"ok": True}), 200
