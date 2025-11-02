from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy.exc import IntegrityError
from app.extension.extensions import db, socketio
from app.models.event import Event, EventStatus
from app.models.provisionalResult import ProvisionalResult
from app.models.winner import Winner

bp_results = Blueprint('results', __name__, url_prefix='/api/vendor/events/<uuid:event_id>/results')

def _vendor_id():
    sub = get_jwt().get("sub") or {}
    return int(sub.get("id"))

def _rooms(vendor_id, event_id):
    return f"vendor_{vendor_id}", f"event_{event_id}"

@bp_results.post('/provisional')
@jwt_required()
def submit_provisional(event_id):
    vid = _vendor_id()
    ev = Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()

    payload = request.get_json() or {}
    team_id = payload.get("team_id")
    rank = payload.get("proposed_rank")
    if not team_id or rank is None:
        return jsonify({"error": "team_id and proposed_rank required"}), 400

    pr = ProvisionalResult(event_id=ev.id, team_id=team_id, proposed_rank=int(rank), submitted_by_vendor=vid)
    db.session.merge(pr)  # merge to allow upsert by (event_id, team_id) via unique constraint
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        # On conflict, update
        db.session.execute(
            db.text("""
                UPDATE provisional_results
                SET proposed_rank = :rank, submitted_by_vendor = :vid
                WHERE event_id = :eid AND team_id = :tid
            """), {"rank": int(rank), "vid": vid, "eid": str(ev.id), "tid": str(team_id)}
        )
        db.session.commit()

    r_vendor, r_event = _rooms(vid, ev.id)
    socketio.emit("provisional_results_updated", {"event_id": str(ev.id)}, room=r_vendor)
    socketio.emit("provisional_results_updated", {"event_id": str(ev.id)}, room=r_event)

    return jsonify({"ok": True}), 201

@bp_results.get('/provisional')
@jwt_required()
def list_provisional(event_id):
    vid = _vendor_id()
    ev = Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()
    rows = (ProvisionalResult.query
            .filter_by(event_id=ev.id)
            .order_by(ProvisionalResult.proposed_rank.asc())
            .all())
    return jsonify([{
        "team_id": str(r.team_id),
        "proposed_rank": r.proposed_rank
    } for r in rows]), 200

@bp_results.post('/publish')
@jwt_required()
def publish_winners(event_id):
    vid = _vendor_id()
    ev = Event.query.filter_by(id=event_id, vendor_id=vid).first_or_404()

    if ev.status == EventStatus.COMPLETED:
        return jsonify({"error": "Event already completed"}), 400

    payload = request.get_json() or {}
    winners = payload.get("winners")  # list of {team_id, rank}
    if not winners or not isinstance(winners, list):
        return jsonify({"error": "winners list required"}), 400

    # Clear existing winners for re-publish scenario
    db.session.query(Winner).filter_by(event_id=ev.id).delete()

    # Insert with rank uniqueness
    for w in winners:
        team_id = w.get("team_id")
        rank = w.get("rank")
        if not team_id or rank is None:
            db.session.rollback()
            return jsonify({"error": "team_id and rank required for each winner"}), 400
        db.session.add(Winner(event_id=ev.id, team_id=team_id, rank=int(rank)))

    # Mark event completed
    ev.status = EventStatus.COMPLETED
    db.session.commit()

    r_vendor, r_event = _rooms(vid, ev.id)
    socketio.emit("winners_published", {"event_id": str(ev.id), "winners": winners}, room=r_vendor)
    socketio.emit("winners_published", {"event_id": str(ev.id), "winners": winners}, room=r_event)

    return jsonify({"ok": True}), 201
