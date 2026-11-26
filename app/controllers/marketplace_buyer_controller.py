"""Cafe identity for buying on the Hash Marketplace (hash-medusa).

The dashboard Shop buys gear on the same Medusa storefront the website uses.
hash-medusa's `hfg-cafe` auth provider calls this endpoint with the dashboard
bearer token to confirm which cafe is signing in, exactly as its `hfg`
provider calls hfg-user-onboard `/api/users` for gamers.

Accepted tokens:
- the owner login token (`sub.type == "vendor"`, `sub.id == vendor_id`), or
- a live staff session token (`scope == "vendor_access"`) whose role holds
  `store.manage` for this cafe.
"""
from datetime import datetime

import jwt
from flask import Blueprint, current_app, jsonify, request

from app.models.vendor import Vendor

bp_marketplace_buyer = Blueprint("marketplace_buyer", __name__, url_prefix="/api/vendor/<int:vendor_id>/marketplace")

BUY_PERMISSION = "store.manage"


class BuyerError(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.message = message
        self.status = status


def _decode(token):
    secret = current_app.config.get("JWT_SECRET_KEY") or "dev"
    try:
        # Login-service tokens carry an object-shaped "sub"; keep signature and expiry checks.
        return jwt.decode(token, secret, algorithms=["HS256"], options={"verify_sub": False})
    except jwt.ExpiredSignatureError:
        raise BuyerError("Your session expired. Sign in again.", 401)
    except jwt.InvalidTokenError:
        raise BuyerError("Invalid session", 401)


def _staff_allowed(claims, vendor_id):
    """True when a vendor_access token is a live session whose role may buy for this cafe."""
    from app.extension.extensions import db
    from app.models.cafe_wallet import CafeStaffSession
    from app.models.vendorStaff import VendorStaff
    from app.services.rbac_service import get_role_permissions

    staff = claims.get("staff") or {}
    session = db.session.get(CafeStaffSession, claims.get("jti"))
    if not session or session.closed_at or session.expires_at <= datetime.utcnow() or session.vendor_id != vendor_id:
        raise BuyerError("Unlock your staff session again", 401)
    role = staff.get("role")
    if role != "owner":
        member = VendorStaff.query.filter_by(id=staff.get("id"), vendor_id=vendor_id, is_active=True).first()
        if not member:
            raise BuyerError("Staff account is disabled", 403)
        role = member.role
    return BUY_PERMISSION in get_role_permissions(vendor_id).get(role, [])


def authorize_buyer(claims, vendor_id, staff_allowed=_staff_allowed):
    """Raise BuyerError unless the token's claims may buy for vendor_id."""
    if not isinstance(claims, dict):
        raise BuyerError("Invalid session", 401)
    if claims.get("scope") == "vendor_access":
        try:
            claim_vid = int(claims.get("vendor_id"))
        except (TypeError, ValueError):
            raise BuyerError("Invalid session", 401)
        if claim_vid != vendor_id:
            raise BuyerError("Vendor mismatch", 403)
        if not staff_allowed(claims, vendor_id):
            raise BuyerError("Your role can't buy from the Shop", 403)
        return
    sub = claims.get("sub")
    if not isinstance(sub, dict) or sub.get("type") != "vendor":
        raise BuyerError("A cafe sign-in is required", 403)
    claim_vid = claims.get("vendor_id", sub.get("id"))
    try:
        claim_vid = int(claim_vid)
    except (TypeError, ValueError):
        raise BuyerError("Invalid session", 401)
    if claim_vid != vendor_id:
        raise BuyerError("Vendor mismatch", 403)


def buyer_profile(vendor):
    contact = vendor.contact_info
    address = vendor.physical_address
    return {
        "vendor_id": vendor.id,
        "cafe_name": (getattr(vendor, "display_name", None) or vendor.cafe_name or "").strip(),
        "owner_name": (vendor.owner_name or "").strip(),
        "email": ((contact.email if contact else "") or "").strip(),
        "phone": ((contact.phone if contact else "") or "").strip(),
        "address": {
            "line1": (address.addressLine1 or "").strip(),
            "line2": (address.addressLine2 or "").strip(),
            "pincode": (address.pincode or "").strip(),
            "state": (address.state or "").strip(),
            "country": (address.country or "India").strip(),
        } if address else None,
    }


@bp_marketplace_buyer.get("/buyer")
def get_marketplace_buyer(vendor_id):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or not auth[7:].strip():
        return jsonify(error="Authorization required"), 401
    try:
        authorize_buyer(_decode(auth[7:].strip()), vendor_id)
    except BuyerError as error:
        return jsonify(error=error.message), error.status
    vendor = Vendor.query.get(vendor_id)
    if not vendor:
        return jsonify(error="Cafe not found"), 404
    response = jsonify(buyer=buyer_profile(vendor))
    response.headers["Cache-Control"] = "private, no-store"
    return response
