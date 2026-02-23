# app/controllers/result_controller.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app.extension.extensions import db
from app.models.event import Event, EventStatus
from app.models.winner import Winner
from app.models.team import Team
from app.models.teamMember import TeamMember
from app.models.user import User

bp_results = Blueprint('results', __name__, url_prefix='/api/vendor/events/<uuid:event_id>/results')

def _vendor_id():
    vendor = get_jwt().get("vendor") or {}
    return int(vendor.get("id"))


def _snapshot_url(value):
    # verified_snapshot is stored as Cloudinary URL (string). Keep backward compatibility.
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        url = value.get("url") or value.get("secure_url")
        return url if isinstance(url, str) else None
    return None


@bp_results.get('/winners')
@jwt_required()
def list_winners(event_id):
    vid = _vendor_id()
    Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()
    winners = Winner.query.filter_by(event_id=event_id).order_by(Winner.rank.asc()).all()

    team_ids = [w.team_id for w in winners]
    teams = Team.query.filter(Team.id.in_(team_ids)).all() if team_ids else []
    team_map = {t.id: t for t in teams}

    members = (
        db.session.query(TeamMember, User)
        .join(User, User.id == TeamMember.user_id)
        .filter(TeamMember.team_id.in_(team_ids))
        .order_by(TeamMember.joined_at.asc())
        .all()
    ) if team_ids else []

    members_by_team = {}
    for tm, user in members:
        members_by_team.setdefault(tm.team_id, []).append({
            "user_id": user.id,
            "name": user.name,
            "game_username": user.game_username,
            "avatar_path": user.avatar_path,
            "role": tm.role,
            "joined_at": tm.joined_at.isoformat() if tm.joined_at else None
        })

    return jsonify([{
        "winner_id": str(w.id),
        "event_id": str(w.event_id),
        "team_id": str(w.team_id),
        "rank": w.rank,
        "published_at": w.published_at.isoformat() if w.published_at else None,
        "team": {
            "id": str(team_map[w.team_id].id) if w.team_id in team_map else str(w.team_id),
            "name": team_map[w.team_id].team_name if w.team_id in team_map else None,
            "is_individual": team_map[w.team_id].is_individual if w.team_id in team_map else None,
            "created_by_user": team_map[w.team_id].created_by_user if w.team_id in team_map else None,
            "member_count": len(members_by_team.get(w.team_id, []))
        },
        "members": members_by_team.get(w.team_id, []),
        "verified_snapshot": _snapshot_url(w.verified_snapshot)
    } for w in winners]), 200

@bp_results.post('/publish')
@jwt_required()
def publish_winners(event_id):
    vid = _vendor_id()
    ev = Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()
    if ev.status == EventStatus.COMPLETED:
        return jsonify({"error": "Event already completed"}), 400
    payload = request.get_json() or {}
    winners = payload.get("winners")
    if not winners or not isinstance(winners, list):
        return jsonify({"error": "winners list required"}), 400
    db.session.query(Winner).filter_by(event_id=event_id).delete()
    for w in winners:
        if not w.get("team_id") or w.get("rank") is None:
            return jsonify({"error": "team_id and rank required"}), 400
        snapshot_url = w.get("verified_snapshot", w.get("result_image_url"))
        if snapshot_url is not None and not isinstance(snapshot_url, str):
            return jsonify({"error": "verified_snapshot must be a Cloudinary image URL string"}), 400
        db.session.add(Winner(
            event_id=event_id,
            team_id=w["team_id"],
            rank=int(w["rank"]),
            verified_snapshot=snapshot_url
        ))
    ev.status = EventStatus.COMPLETED
    db.session.commit()
    return jsonify({"ok": True}), 201
