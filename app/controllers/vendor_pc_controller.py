from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy.exc import SQLAlchemyError
from app.services.link_service import list_vendor_pcs, create_link, close_link
from app.services.subscription_service import get_vendor_pc_limit
from app.models.console_link_session import ConsoleLinkSession

bp_vendor_pc = Blueprint('vendor_pc', __name__, url_prefix='/api/vendors/<int:vendor_id>/pcs')

def _auth_vendor(vendor_id):
    # optional: check JWT claim vendor_id == path vendor_id
    return True

@bp_vendor_pc.get('/')
def get_pcs(vendor_id):
    try:
        _auth_vendor(vendor_id)
        pcs = list_vendor_pcs(vendor_id)

        try:
            limit = get_vendor_pc_limit(vendor_id)
        except SQLAlchemyError:
            current_app.logger.exception(
                "Subscription lookup failed for vendor_id=%s, using default limit", vendor_id
            )
            limit = 3

        active_console_ids = set()
        try:
            active_console_ids = {
                row[0] for row in ConsoleLinkSession.query.with_entities(ConsoleLinkSession.console_id)
                .filter_by(vendor_id=vendor_id, status='active')
                .all()
            }
            active = len(active_console_ids)
        except SQLAlchemyError:
            current_app.logger.exception(
                "Active link lookup failed for vendor_id=%s, using zero links", vendor_id
            )
            active = 0

        return jsonify({
            "plan_limit": limit,
            "active_links": active,
            "remaining_capacity": max(0, limit - active),
            "pcs": [{
                "id": c.id, "number": c.console_number, "brand": c.brand, "model": c.model_number,
                "linked": c.id in active_console_ids
            } for c in pcs]
        }), 200
    except SQLAlchemyError as e:
        current_app.logger.exception(
            "Database error while fetching vendor PCs for vendor_id=%s", vendor_id
        )
        return jsonify({
            "error": "Failed to fetch PCs due to a database issue",
            "details": str(e)
        }), 500
    except Exception as e:
        current_app.logger.exception(
            "Unexpected error while fetching vendor PCs for vendor_id=%s", vendor_id
        )
        return jsonify({
            "error": "Failed to fetch PCs",
            "details": str(e)
        }), 500

@bp_vendor_pc.post('/link')
def link_pc(vendor_id):
    try:
        _auth_vendor(vendor_id)
        data = request.get_json(silent=True) or {}
        console_id = data.get('console_id')
        if console_id is None:
            return jsonify({"error": "console_id is required"}), 400

        sess, err = create_link(vendor_id, console_id, kiosk_id=data.get('kiosk_id'))
        if err:
            return jsonify({"error": err}), 409
        return jsonify({
            "session_token": sess.session_token,
            "ws_url": f"wss://your-host/ws?token={sess.session_token}"
        }), 201
    except SQLAlchemyError as e:
        current_app.logger.exception("Database error while linking PC for vendor_id=%s", vendor_id)
        return jsonify({"error": "Failed to link PC due to a database issue", "details": str(e)}), 500
    except Exception as e:
        current_app.logger.exception("Unexpected error while linking PC for vendor_id=%s", vendor_id)
        return jsonify({"error": "Failed to link PC", "details": str(e)}), 500

@bp_vendor_pc.post('/unlink')
def unlink_pc(vendor_id):
    try:
        _auth_vendor(vendor_id)
        data = request.get_json(silent=True) or {}
        if data.get('session_id') is None and data.get('console_id') is None:
            return jsonify({"error": "Either session_id or console_id is required"}), 400

        closed = close_link(
            session_id=data.get('session_id'),
            console_id=data.get('console_id'),
            vendor_id=vendor_id,
            reason="manual"
        )
        return jsonify({"closed": closed}), 200
    except SQLAlchemyError as e:
        current_app.logger.exception("Database error while unlinking PC for vendor_id=%s", vendor_id)
        return jsonify({"error": "Failed to unlink PC due to a database issue", "details": str(e)}), 500
    except Exception as e:
        current_app.logger.exception("Unexpected error while unlinking PC for vendor_id=%s", vendor_id)
        return jsonify({"error": "Failed to unlink PC", "details": str(e)}), 500
