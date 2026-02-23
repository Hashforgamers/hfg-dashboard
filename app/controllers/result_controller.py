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


def _default_platform_profiles():
    return {
        "pc": {},
        "ps": {},
        "xbox": {},
        "vr": {}
    }


def _build_verified_snapshot(payload):
    if isinstance(payload.get("verified_snapshot"), dict):
        snapshot = dict(payload["verified_snapshot"])
    else:
        snapshot = {}

    platform_profiles = snapshot.get("platform_profiles")
    if not isinstance(platform_profiles, dict):
        platform_profiles = _default_platform_profiles()
    else:
        for k in ("pc", "ps", "xbox", "vr"):
            if k not in platform_profiles or not isinstance(platform_profiles[k], dict):
                platform_profiles[k] = {}

    # Convenience fields for common winners payload shapes.
    if payload.get("platform"):
        snapshot["platform"] = payload.get("platform")
    if payload.get("game_title"):
        snapshot["game_title"] = payload.get("game_title")
    if payload.get("score") is not None:
        snapshot["score"] = payload.get("score")
    if payload.get("stats") is not None:
        snapshot["stats"] = payload.get("stats")
    if payload.get("highlights") is not None:
        snapshot["highlights"] = payload.get("highlights")

    # Allow direct short-hand profile keys in publish payload.
    for platform_key in ("pc", "ps", "xbox", "vr"):
        if isinstance(payload.get(platform_key), dict):
            platform_profiles[platform_key] = payload.get(platform_key)

    snapshot["platform_profiles"] = platform_profiles
    return snapshot


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
        "verified_snapshot": {
            **(_build_verified_snapshot({"verified_snapshot": w.verified_snapshot}) if w.verified_snapshot else {"platform_profiles": _default_platform_profiles()})
        }
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
        db.session.add(Winner(
            event_id=event_id,
            team_id=w["team_id"],
            rank=int(w["rank"]),
            verified_snapshot=_build_verified_snapshot(w)
        ))
    ev.status = EventStatus.COMPLETED
    db.session.commit()
    return jsonify({"ok": True}), 201
