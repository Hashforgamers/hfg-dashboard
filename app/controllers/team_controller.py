# app/controllers/team_controller.py
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app.models.event import Event
from app.models.team import Team
from app.models.teamMember import TeamMember

bp_teams = Blueprint('teams', __name__, url_prefix='/api/vendor/events/<uuid:event_id>/teams')

def _vendor_id():
    vendor = get_jwt().get("vendor") or {}
    return int(vendor.get("id"))

@bp_teams.get('/')
@jwt_required()
def list_teams(event_id):
    vid = _vendor_id()
    Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()
    teams = Team.query.filter_by(event_id=event_id).order_by(Team.created_at.asc()).all()
    return jsonify([{
        "id": str(t.id),
        "name": t.team_name,
        "created_by_user": t.created_by_user,
        "created_at": t.created_at.isoformat(),
        "is_individual": t.is_individual
    } for t in teams]), 200

@bp_teams.get('/<uuid:team_id>/members')
@jwt_required()
def list_members(event_id, team_id):
    vid = _vendor_id()
    Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()
    members = (TeamMember.query
               .filter_by(team_id=team_id)
               .order_by(TeamMember.joined_at.asc())
               .all())
    return jsonify([{
        "user_id": m.user_id, "role": m.role, "joined_at": m.joined_at.isoformat()
    } for m in members]), 200
