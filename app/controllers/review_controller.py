from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import text
from datetime import datetime, timezone

from app.extension.extensions import db
from app.models.cafeReview import CafeReview
from app.models.user import User
from app.services.websocket_service import socketio

bp_reviews = Blueprint("reviews", __name__, url_prefix="/api/vendor/reviews")


def _vendor_id():
    vendor = get_jwt().get("vendor") or {}
    return int(vendor.get("id"))


def _staff_name():
    staff = get_jwt().get("staff") or {}
    return staff.get("name") or "Owner"


@bp_reviews.get("/")
@jwt_required()
def list_reviews():
    vid = _vendor_id()
    status = (request.args.get("status") or "all").lower()
    rating = request.args.get("rating")
    search = (request.args.get("search") or "").strip().lower()
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = max(int(request.args.get("offset", 0)), 0)

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
    }), 200


@bp_reviews.get("/summary")
@jwt_required()
def reviews_summary():
    vid = _vendor_id()
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
    }), 200


@bp_reviews.patch("/<uuid:review_id>/response")
@jwt_required()
def respond_review(review_id):
    vid = _vendor_id()
    data = request.get_json(silent=True) or {}
    response_text = (data.get("response_text") or "").strip()
    if not response_text:
        return jsonify({"error": "response_text is required"}), 400

    review = CafeReview.query.filter_by(id=review_id, vendor_id=vid).first()
    if not review:
        return jsonify({"error": "Review not found"}), 404

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
    vid = _vendor_id()
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip().lower()
    if status not in {"published", "hidden"}:
        return jsonify({"error": "status must be published or hidden"}), 400

    review = CafeReview.query.filter_by(id=review_id, vendor_id=vid).first()
    if not review:
        return jsonify({"error": "Review not found"}), 404

    review.status = status
    db.session.commit()
    try:
        socketio.emit("reviews_updated", {"vendor_id": vid}, room=f"vendor_{vid}")
    except Exception:
        pass
    return jsonify({"ok": True}), 200
