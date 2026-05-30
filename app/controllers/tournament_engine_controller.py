from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt

from app.models.event import Event
from app.models.tournamentMatch import TournamentMatch
from app.services.websocket_service import socketio
from app.services.tournament_engine_service import (
    admin_result,
    close_check_in,
    generate_single_elimination_bracket,
    get_bracket,
    list_matches,
    open_check_in,
    resolve_dispute,
    start_match,
    update_match,
)


bp_tournament_engine = Blueprint("tournament_engine", __name__, url_prefix="/api/vendor/events/<uuid:event_id>")


def _vendor_id():
    vendor = get_jwt().get("vendor") or {}
    return int(vendor.get("id"))


def _event_for_vendor(event_id):
    return Event.query.filter_by(id=event_id, vendor_id=_vendor_id()).first_or_404()


def _emit(vid):
    try:
        socketio.emit("tournaments_updated", {"vendor_id": vid}, room=f"vendor_{vid}")
    except Exception:
        pass


@bp_tournament_engine.post("/check-in/open")
@jwt_required()
def open_event_check_in(event_id):
    event = _event_for_vendor(event_id)
    open_check_in(event)
    _emit(_vendor_id())
    return jsonify({"ok": True, "check_in_starts_at": event.check_in_starts_at.isoformat()}), 200


@bp_tournament_engine.post("/check-in/close")
@jwt_required()
def close_event_check_in(event_id):
    event = _event_for_vendor(event_id)
    close_check_in(event)
    _emit(_vendor_id())
    return jsonify({"ok": True, "check_in_ends_at": event.check_in_ends_at.isoformat()}), 200


@bp_tournament_engine.post("/bracket/generate")
@jwt_required()
def generate_bracket(event_id):
    event = _event_for_vendor(event_id)
    payload = request.get_json(silent=True) or {}
    try:
        bracket = generate_single_elimination_bracket(
            event,
            require_check_in=bool(payload.get("require_check_in", False)),
            force=bool(payload.get("force", False)),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    _emit(_vendor_id())
    return jsonify(bracket), 201


@bp_tournament_engine.get("/bracket")
@jwt_required()
def get_event_bracket(event_id):
    _event_for_vendor(event_id)
    return jsonify(get_bracket(event_id)), 200


@bp_tournament_engine.get("/matches")
@jwt_required()
def get_event_matches(event_id):
    _event_for_vendor(event_id)
    return jsonify(list_matches(event_id)), 200


@bp_tournament_engine.patch("/matches/<uuid:match_id>")
@jwt_required()
def patch_match(event_id, match_id):
    _event_for_vendor(event_id)
    match = TournamentMatch.query.filter_by(id=match_id, event_id=event_id).first_or_404()
    return jsonify(update_match(match, request.get_json(silent=True) or {})), 200


@bp_tournament_engine.post("/matches/<uuid:match_id>/start")
@jwt_required()
def start_event_match(event_id, match_id):
    event = _event_for_vendor(event_id)
    match = TournamentMatch.query.filter_by(id=match_id, event_id=event_id).first_or_404()
    try:
        payload = start_match(event, match)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    _emit(_vendor_id())
    return jsonify(payload), 200


@bp_tournament_engine.post("/matches/<uuid:match_id>/admin-result")
@jwt_required()
def admin_match_result(event_id, match_id):
    event = _event_for_vendor(event_id)
    match = TournamentMatch.query.filter_by(id=match_id, event_id=event_id).first_or_404()
    try:
        payload = admin_result(event, match, _vendor_id(), request.get_json(silent=True) or {})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    _emit(_vendor_id())
    return jsonify(payload), 200


@bp_tournament_engine.post("/matches/<uuid:match_id>/resolve-dispute")
@jwt_required()
def resolve_match_dispute(event_id, match_id):
    event = _event_for_vendor(event_id)
    match = TournamentMatch.query.filter_by(id=match_id, event_id=event_id).first_or_404()
    payload = resolve_dispute(event, match, _vendor_id(), request.get_json(silent=True) or {})
    _emit(_vendor_id())
    return jsonify(payload), 200
