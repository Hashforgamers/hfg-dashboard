from flask import Blueprint, request, jsonify, current_app
import time, datetime
import jwt  # PyJWT
from flask_jwt_extended import jwt_required, get_jwt
from app.services.event_service import create_event, list_events, update_event
from app.services.cloudinary_event_service import CloudinaryEventImageService
from app.services.websocket_service import socketio
from app.extension.extensions import db

bp_events = Blueprint('events', __name__, url_prefix='/api/vendor/events')

def _vendor_id():
    vendor = get_jwt().get("vendor") or {}
    return int(vendor.get("id"))

@bp_events.post('/getJwt')
def issue_jwt():   # ✅ renamed function to avoid shadowing
    """
    Issue a short-lived JWT for vendor or service-to-service calls.
    Body (JSON):
    {
      "vendor_id": 14,
      "type": "vendor",
      "ttl_minutes": 480,
      "extra": { "email": "owner@x" }
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        vendor_id = data.get("vendor_id")
        ttl_minutes = int(data.get("ttl_minutes") or 480)
        extra = data.get("extra") or {}

        if not vendor_id:
            return jsonify({"error": "vendor_id is required"}), 400
        if ttl_minutes <= 0 or ttl_minutes > 24*60:
            return jsonify({"error": "ttl_minutes must be in 1..1440"}), 400

        secret = current_app.config.get("JWT_SECRET_KEY")
        alg = current_app.config.get("JWT_ALGORITHM", "HS256")
        if not secret:
            return jsonify({"error": "Server JWT not configured"}), 500

        now = int(time.time())
        exp = now + ttl_minutes * 60

        payload = {
            "sub": str(vendor_id),
            "vendor": {"id": int(vendor_id)},
            "iat": now,
            "exp": exp,
        }

        for k, v in extra.items():
            if k not in {"sub", "iat", "exp"}:
                payload[k] = v

        token = jwt.encode(payload, secret, algorithm=alg)
        return jsonify({
            "token": token,
            "token_type": "Bearer",
            "expires_in": ttl_minutes * 60,
            "vendor_id": int(vendor_id)
        }), 201

    except Exception as e:
        current_app.logger.exception("issue_jwt error")
        return jsonify({"error": "failed_to_issue_token", "detail": str(e)}), 500


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
        "start_at": e.start_at.isoformat(), "end_at": e.end_at.isoformat() ,
        "banner_image_url":  e.banner_image_url, "banner_public_id":  e.banner_public_id,
    } for e in items]), 200

@bp_events.patch('/<uuid:event_id>')
@jwt_required()
def patch_event(event_id):
    vid = _vendor_id()
    ev = update_event(vid, event_id, request.get_json() or {})
    socketio.emit("event_updated", {"event_id": str(ev.id), "status": ev.status}, room=f"vendor_{vid}")
    return jsonify({"ok": True}), 200

@bp_events.post('/upload-banner')
@jwt_required()
def upload_banner():
    """
    Upload event banner image to Cloudinary.
    Accepts: multipart/form-data
      - image (file)           ← required
      - event_title (string)   ← optional, used for public_id naming
    Returns: { url, public_id }
    """
    vid         = _vendor_id()
    image_file  = request.files.get('image')
    event_title = request.form.get('event_title', 'event')

    if not image_file:
        return jsonify({"error": "image file is required"}), 400

    result = CloudinaryEventImageService.upload_event_banner(image_file, vid, event_title)

    if not result['success']:
        return jsonify({"error": result['error']}), 400

    return jsonify({
        "url":        result['url'],
        "public_id":  result['public_id']
    }), 200


@bp_events.delete('/delete-banner')
@jwt_required()
def delete_banner():
    """
    Delete event banner from Cloudinary.
    Body: { "public_id": "EVENT_BANNERS/..." }
    """
    data      = request.get_json(silent=True) or {}
    public_id = data.get('public_id')

    if not public_id:
        return jsonify({"error": "public_id is required"}), 400

    result = CloudinaryEventImageService.delete_event_banner(public_id)

    if not result['success']:
        return jsonify({"error": result['error']}), 400

    return jsonify({"ok": True}), 200
