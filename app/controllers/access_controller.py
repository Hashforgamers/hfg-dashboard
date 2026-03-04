import os
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy.exc import IntegrityError

from app.extension.extensions import db
from app.models.vendor import Vendor
from app.models.vendorStaff import VendorStaff
from app.services.rbac_service import (
    ALL_PERMISSIONS,
    VALID_ROLES,
    claim_vendor_id,
    claims_permissions,
    create_access_token_payload,
    create_staff,
    generate_unique_pin,
    get_role_permissions,
    reset_role_permissions,
    set_role_permissions,
    verify_staff_pin,
)
from werkzeug.security import generate_password_hash


bp_access = Blueprint("vendor_access", __name__, url_prefix="/api/vendor/<int:vendor_id>/access")


def _ensure_vendor_exists(vendor_id: int):
    vendor = Vendor.query.get(vendor_id)
    if not vendor:
        return None, (jsonify({"error": "Vendor not found"}), 404)
    return vendor, None


def _auth_debug(message: str, **meta):
    try:
        current_app.logger.info("[RBAC_DEBUG] %s | %s", message, meta)
    except Exception:
        pass


def _require_permission(vendor_id: int, permission: str):
    claims = get_jwt() or {}
    claim_vid = claim_vendor_id(claims)
    _auth_debug(
        "permission_check",
        vendor_id=vendor_id,
        claim_vendor_id=claim_vid,
        required_permission=permission,
        has_staff_claim=bool((claims or {}).get("staff")),
    )
    if claim_vid is not None and claim_vid != vendor_id:
        return jsonify({"error": "Vendor mismatch"}), 403

    permissions = claims_permissions(claims, vendor_id)
    _auth_debug(
        "permission_check_resolved",
        vendor_id=vendor_id,
        permission_count=len(permissions),
        permissions_preview=permissions[:5],
    )
    if permission not in permissions:
        return jsonify({"error": "Forbidden", "required_permission": permission}), 403
    return None


@bp_access.post("/session/owner")
def issue_owner_session(vendor_id: int):
    _, err = _ensure_vendor_exists(vendor_id)
    if err:
        return err

    auth_header = request.headers.get("Authorization", "")
    _auth_debug(
        "session_owner_start",
        vendor_id=vendor_id,
        has_auth_header=bool(auth_header),
        auth_prefix=(auth_header[:12] if auth_header else None),
    )
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Authorization header missing"}), 401

    token = auth_header.split(" ", 1)[1].strip()
    secret = os.getenv("JWT_SECRET_KEY", "dev")

    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"])
        _auth_debug(
            "session_owner_decode_ok",
            vendor_id=vendor_id,
            claim_keys=list((claims or {}).keys()),
            sub_type=type((claims or {}).get("sub")).__name__,
        )
    except ExpiredSignatureError:
        _auth_debug("session_owner_decode_expired", vendor_id=vendor_id)
        return jsonify({"error": "Token expired"}), 401
    except InvalidTokenError:
        _auth_debug("session_owner_decode_invalid", vendor_id=vendor_id)
        return jsonify({"error": "Invalid token"}), 401

    sub = claims.get("sub") or {}
    claim_vid = None
    owner_name = "Owner"

    if isinstance(sub, dict):
        if sub.get("id") is not None:
            claim_vid = int(sub["id"])
        if sub.get("name"):
            owner_name = str(sub["name"])
    elif isinstance(sub, str):
        # Handle newer string-sub tokens
        if sub.isdigit():
            claim_vid = int(sub)

    # Also accept explicit vendor_id claim when present
    if claims.get("vendor_id") is not None:
        try:
            claim_vid = int(claims.get("vendor_id"))
        except (TypeError, ValueError):
            pass

    _auth_debug(
        "session_owner_claims_resolved",
        vendor_id=vendor_id,
        claim_vendor_id=claim_vid,
        owner_name=owner_name,
    )
    if claim_vid is not None and claim_vid != vendor_id:
        return jsonify({"error": "Vendor mismatch"}), 403

    payload = create_access_token_payload(
        vendor_id=vendor_id,
        staff_id=f"owner-{vendor_id}",
        name=owner_name,
        role="owner",
    )
    return jsonify(payload), 200


@bp_access.post("/unlock")
def unlock_staff_session(vendor_id: int):
    _, err = _ensure_vendor_exists(vendor_id)
    if err:
        return err

    body = request.get_json(silent=True) or {}
    pin = str(body.get("pin", "")).strip()
    _auth_debug("unlock_start", vendor_id=vendor_id, pin_length=len(pin))
    if not pin:
        return jsonify({"error": "pin is required"}), 400

    staff = verify_staff_pin(vendor_id, pin)
    if not staff:
        _auth_debug("unlock_failed_invalid_pin", vendor_id=vendor_id)
        return jsonify({"error": "Invalid PIN"}), 401

    _auth_debug("unlock_success", vendor_id=vendor_id, staff_id=staff.id, role=staff.role)
    payload = create_access_token_payload(
        vendor_id=vendor_id,
        staff_id=staff.id,
        name=staff.name,
        role=staff.role,
    )
    return jsonify(payload), 200


@bp_access.get("/staff")
@jwt_required()
def list_staff(vendor_id: int):
    gate = _require_permission(vendor_id, "staff.manage")
    if gate:
        return gate

    records = (
        VendorStaff.query
        .filter_by(vendor_id=vendor_id)
        .order_by(VendorStaff.created_at.asc())
        .all()
    )
    return jsonify([r.to_dict() for r in records]), 200


@bp_access.post("/staff")
@jwt_required()
def create_staff_member(vendor_id: int):
    gate = _require_permission(vendor_id, "staff.manage")
    if gate:
        return gate

    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    role = str(body.get("role", "staff")).strip().lower()

    if not name:
        return jsonify({"error": "name is required"}), 400
    if role not in VALID_ROLES or role == "owner":
        return jsonify({"error": "role must be staff or manager"}), 400

    try:
        created = create_staff(vendor_id, name, role)
        return jsonify(created), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Employee with same name already exists"}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp_access.patch("/staff/<int:staff_id>")
@jwt_required()
def update_staff_member(vendor_id: int, staff_id: int):
    gate = _require_permission(vendor_id, "staff.manage")
    if gate:
        return gate

    staff = VendorStaff.query.filter_by(id=staff_id, vendor_id=vendor_id).first()
    if not staff:
        return jsonify({"error": "Staff not found"}), 404

    body = request.get_json(silent=True) or {}

    if "name" in body:
        name = str(body.get("name", "")).strip()
        if not name:
            return jsonify({"error": "name cannot be empty"}), 400
        staff.name = name

    if "role" in body:
        role = str(body.get("role", "")).strip().lower()
        if role not in VALID_ROLES or role == "owner":
            return jsonify({"error": "role must be staff or manager"}), 400
        staff.role = role

    if "is_active" in body:
        staff.is_active = bool(body.get("is_active"))

    generated_pin = None
    if body.get("regenerate_pin") is True:
        generated_pin = generate_unique_pin(vendor_id)
        staff.pin_hash = generate_password_hash(generated_pin)

    db.session.commit()

    payload = staff.to_dict()
    if generated_pin:
        payload["generated_pin"] = generated_pin
    return jsonify(payload), 200


@bp_access.delete("/staff/<int:staff_id>")
@jwt_required()
def delete_staff_member(vendor_id: int, staff_id: int):
    gate = _require_permission(vendor_id, "staff.manage")
    if gate:
        return gate

    staff = VendorStaff.query.filter_by(id=staff_id, vendor_id=vendor_id).first()
    if not staff:
        return jsonify({"error": "Staff not found"}), 404

    db.session.delete(staff)
    db.session.commit()
    return jsonify({"deleted": True, "id": staff_id}), 200


@bp_access.get("/role-permissions")
@jwt_required()
def get_permissions(vendor_id: int):
    gate = _require_permission(vendor_id, "staff.manage")
    if gate:
        return gate

    matrix = get_role_permissions(vendor_id)
    return jsonify({
        "permissions": ALL_PERMISSIONS,
        "matrix": matrix,
    }), 200


@bp_access.put("/role-permissions")
@jwt_required()
def update_permissions(vendor_id: int):
    gate = _require_permission(vendor_id, "staff.manage")
    if gate:
        return gate

    body = request.get_json(silent=True) or {}
    matrix = body.get("matrix")
    if not isinstance(matrix, dict):
        return jsonify({"error": "matrix must be an object"}), 400

    updated = set_role_permissions(vendor_id, matrix)
    return jsonify({"matrix": updated}), 200


@bp_access.delete("/role-permissions")
@jwt_required()
def reset_permissions(vendor_id: int):
    gate = _require_permission(vendor_id, "staff.manage")
    if gate:
        return gate

    matrix = reset_role_permissions(vendor_id)
    return jsonify({"matrix": matrix}), 200
