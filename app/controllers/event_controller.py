from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app.services.event_service import create_event, list_events, update_event
from app.extension.extensions import socketio

bp_events = Blueprint('events', __name__, url_prefix='/api/vendor/events')

def _vendor_id():
    sub = get_jwt().get("sub") or {}
    return int(sub.get("id"))

@bp_events.post('/')
@jwt_required()
def post_event():
    vid = _vendor_id()
    payload = request.get_json()
    ev = create_event(vid, payload)
    socketio.emit("event_created", {"event_id": str(ev.id), "title": ev.title}, room=f"vendor_{vid}")
    return jsonify({"id": str(ev.id)}), 201

@bp_events.get('/')
@jwt_required()
def get_events():
    vid = _vendor_id()
    status = request.args.get("status")
    items = list_events(vid, status)
    return jsonify([{
        "id": str(e.id), "title": e.title, "status": e.status,
        "start_at": e.start_at.isoformat(), "end_at": e.end_at.isoformat()
    } for e in items]), 200

@bp_events.patch('/<uuid:event_id>')
@jwt_required()
def patch_event(event_id):
    vid = _vendor_id()
    ev = update_event(vid, event_id, request.get_json() or {})
    socketio.emit("event_updated", {"event_id": str(ev.id), "status": ev.status}, room=f"vendor_{vid}")
    return jsonify({"ok": True}), 200
