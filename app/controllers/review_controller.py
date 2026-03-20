import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import text
from datetime import datetime, timezone
import requests
from typing import Optional

from app.extension.extensions import db
from app.models.cafeReview import CafeReview
from app.models.user import User
from app.services.websocket_service import socketio

bp_reviews = Blueprint("reviews", __name__, url_prefix="/api/vendor/reviews")


def _vendor_id():
    claims = get_jwt() or {}
    vendor_claim = claims.get("vendor") or {}

    candidate = (
        vendor_claim.get("id")
        or claims.get("vendor_id")
        or claims.get("vendorId")
        or request.args.get("vendor_id")
    )
    if candidate is None:
        payload = request.get_json(silent=True) or {}
        candidate = payload.get("vendor_id")

    if candidate is None:
        raise ValueError("vendor_id missing in token and request")
    try:
        return int(candidate)
    except (TypeError, ValueError):
        raise ValueError("vendor_id is invalid")


def _staff_name():
    staff = get_jwt().get("staff") or {}
    return staff.get("name") or "Owner"


def _user_onboard_base_url() -> str:
    return (os.getenv("USER_ONBOARD_URL") or "https://hfg-user-onboard.onrender.com").rstrip("/")


def _sync_key() -> str:
    return (os.getenv("REVIEW_SYNC_KEY") or "").strip()


def _proxy_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    key = _sync_key()
    if key:
        headers["x-review-sync-key"] = key
    return headers


def _proxy_get(path: str, params: Optional[dict] = None):
    key = _sync_key()
    if not key:
        return False, {"error": "REVIEW_SYNC_KEY not configured"}, 503
    url = f"{_user_onboard_base_url()}{path}"
    try:
        response = requests.get(url, headers=_proxy_headers(), params=params or {}, timeout=8)
    except requests.RequestException as exc:
        return False, {"error": f"user-onboard unreachable: {exc}"}, 502
    try:
        body = response.json()
    except Exception:
        body = {"error": response.text}
    return response.ok, body, response.status_code


def _proxy_patch(path: str, payload: dict):
    key = _sync_key()
    if not key:
        return False, {"error": "REVIEW_SYNC_KEY not configured"}, 503
    url = f"{_user_onboard_base_url()}{path}"
    try:
        response = requests.patch(url, headers=_proxy_headers(), json=payload, timeout=8)
    except requests.RequestException as exc:
        return False, {"error": f"user-onboard unreachable: {exc}"}, 502
    try:
        body = response.json()
    except Exception:
        body = {"error": response.text}
    return response.ok, body, response.status_code


@bp_reviews.get("/")
@jwt_required()
def list_reviews():
    try:
        vid = _vendor_id()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    status = (request.args.get("status") or "all").lower()
    rating = request.args.get("rating")
    search = (request.args.get("search") or "").strip().lower()
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = max(int(request.args.get("offset", 0)), 0)

    ok, body, status_code = _proxy_get(
        f"/api/internal/vendors/{vid}/reviews",
        params={
            "status": status,
            "rating": rating,
            "search": search,
            "limit": limit,
            "offset": offset,
        },
    )
    if ok:
        return jsonify(body), 200

    query = (
        db.session.query(CafeReview, User)
        .outerjoin(User, User.id == CafeReview.user_id)
        .filter(CafeReview.vendor_id == vid)
    )

    if status in {"published", "hidden"}:
        query = query.filter(CafeReview.status == status)
    if rating:
        try:
            rating_val = int(rating)
            query = query.filter(CafeReview.rating == rating_val)
        except ValueError:
            pass
    if search:
        query = query.filter(
            (CafeReview.comment.ilike(f"%{search}%")) |
            (CafeReview.title.ilike(f"%{search}%")) |
            (User.name.ilike(f"%{search}%"))
        )

    rows = query.order_by(CafeReview.created_at.desc()).offset(offset).limit(limit).all()

    payload = []
    for review, user in rows:
        is_anon = bool(review.is_anonymous)
        payload.append({
            "id": str(review.id),
            "vendor_id": review.vendor_id,
            "rating": review.rating,
            "title": review.title,
            "comment": review.comment,
            "status": review.status,
            "created_at": review.created_at.isoformat() if review.created_at else None,
            "response_text": review.response_text,
            "responded_at": review.responded_at.isoformat() if review.responded_at else None,
            "user": {
                "id": None if is_anon else review.user_id,
                "name": "Anonymous" if is_anon else (review.user_name_snapshot or (user.name if user else None)),
                "avatar": None if is_anon else (review.user_avatar_snapshot or (user.avatar_path if user else None)),
                "game_username": None if is_anon else (user.game_username if user else None),
            },
        })

    return jsonify({
        "items": payload,
        "limit": limit,
        "offset": offset,
        "count": len(payload),
        "source": "dashboard_db_fallback",
        "proxy_error": body,
        "proxy_status": status_code,
    }), 200


@bp_reviews.get("/summary")
@jwt_required()
def reviews_summary():
    try:
        vid = _vendor_id()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    ok, body, status_code = _proxy_get(f"/api/internal/vendors/{vid}/reviews/summary")
    if ok:
        return jsonify(body), 200

    row = db.session.execute(text("""
        SELECT
            COUNT(*)::int AS total,
            COALESCE(AVG(rating), 0) AS average,
            SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END)::int AS r5,
            SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END)::int AS r4,
            SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END)::int AS r3,
            SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END)::int AS r2,
            SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END)::int AS r1
        FROM cafe_reviews
        WHERE vendor_id = :vendor_id AND status = 'published'
    """), {"vendor_id": vid}).mappings().first()

    return jsonify({
        "total": int(row["total"] or 0) if row else 0,
        "average": float(row["average"] or 0) if row else 0,
        "r1": int(row["r1"] or 0) if row else 0,
        "r2": int(row["r2"] or 0) if row else 0,
        "r3": int(row["r3"] or 0) if row else 0,
        "r4": int(row["r4"] or 0) if row else 0,
        "r5": int(row["r5"] or 0) if row else 0,
        "source": "dashboard_db_fallback",
        "proxy_error": body,
        "proxy_status": status_code,
    }), 200


@bp_reviews.patch("/<uuid:review_id>/response")
@jwt_required()
def respond_review(review_id):
    try:
        vid = _vendor_id()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    data = request.get_json(silent=True) or {}
    response_text = (data.get("response_text") or "").strip()
    if not response_text:
        return jsonify({"error": "response_text is required"}), 400

    ok, body, status_code = _proxy_patch(
        f"/api/internal/reviews/{review_id}/response",
        {
            "vendor_id": vid,
            "response_text": response_text,
            "responded_by": _staff_name(),
        },
    )
    if ok:
        try:
            socketio.emit("reviews_updated", {"vendor_id": vid}, room=f"vendor_{vid}")
        except Exception:
            pass
        return jsonify({"ok": True}), 200

    review = CafeReview.query.filter_by(id=review_id, vendor_id=vid).first()
    if not review:
        return jsonify({"error": "Review not found", "proxy_error": body, "proxy_status": status_code}), 404

    review.response_text = response_text
    review.responded_at = datetime.now(timezone.utc)
    review.responded_by = _staff_name()
    db.session.commit()
    try:
        socketio.emit("reviews_updated", {"vendor_id": vid}, room=f"vendor_{vid}")
    except Exception:
        pass
    return jsonify({"ok": True}), 200


@bp_reviews.patch("/<uuid:review_id>/status")
@jwt_required()
def update_review_status(review_id):
    try:
        vid = _vendor_id()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip().lower()
    if status not in {"published", "hidden"}:
        return jsonify({"error": "status must be published or hidden"}), 400

    ok, body, status_code = _proxy_patch(
        f"/api/internal/reviews/{review_id}/status",
        {
            "vendor_id": vid,
            "status": status,
        },
    )
    if ok:
        try:
            socketio.emit("reviews_updated", {"vendor_id": vid}, room=f"vendor_{vid}")
        except Exception:
            pass
        return jsonify({"ok": True}), 200

    review = CafeReview.query.filter_by(id=review_id, vendor_id=vid).first()
    if not review:
        return jsonify({"error": "Review not found", "proxy_error": body, "proxy_status": status_code}), 404

    review.status = status
    db.session.commit()
    try:
        socketio.emit("reviews_updated", {"vendor_id": vid}, room=f"vendor_{vid}")
    except Exception:
        pass
    return jsonify({"ok": True}), 200
