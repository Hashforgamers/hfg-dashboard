# app/controllers/result_controller.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app.extension.extensions import db
from app.models.event import Event, EventStatus
from app.models.provisionalResult import ProvisionalResult
from app.models.winner import Winner

bp_results = Blueprint('results', __name__, url_prefix='/api/vendor/events/<uuid:event_id>/results')

def _vendor_id():
    vendor = get_jwt().get("vendor") or {}
    return int(vendor.get("id"))

@bp_results.get('/provisional')
@jwt_required()
def list_provisional(event_id):
    vid = _vendor_id()
    Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()
    rows = (ProvisionalResult.query
            .filter_by(event_id=event_id)
            .order_by(ProvisionalResult.proposed_rank.asc())
            .all())
    return jsonify([{
        "team_id": str(r.team_id),
        "proposed_rank": r.proposed_rank
    } for r in rows]), 200

@bp_results.get('/winners')
@jwt_required()
def list_winners(event_id):
    vid = _vendor_id()
    Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()
    winners = Winner.query.filter_by(event_id=event_id).order_by(Winner.rank.asc()).all()
    return jsonify([{
        "team_id": str(w.team_id),
        "rank": w.rank
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
        db.session.add(Winner(event_id=event_id, team_id=w["team_id"], rank=int(w["rank"])))
    ev.status = EventStatus.COMPLETED
    db.session.commit()
    return jsonify({"ok": True}), 201
