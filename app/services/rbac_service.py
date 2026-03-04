import random
from typing import Dict, List, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token

from app.extension.extensions import db
from app.models.vendorStaff import VendorStaff
from app.models.vendorRolePermission import VendorRolePermission


Permission = str
Role = str

ALL_PERMISSIONS: List[Permission] = [
    "dashboard.view",
    "gaming.manage",
    "booking.manage",
    "transactions.view",
    "extras.manage",
    "gamers.view",
    "pricing.manage",
    "passes.manage",
    "store.manage",
    "games.manage",
    "tournaments.manage",
    "account.manage",
    "staff.manage",
    "subscription.manage",
    "cafe.switch",
]

DEFAULT_ROLE_PERMISSIONS: Dict[Role, List[Permission]] = {
    "owner": ALL_PERMISSIONS,
    "manager": [
        "dashboard.view",
        "gaming.manage",
        "booking.manage",
        "transactions.view",
        "extras.manage",
        "gamers.view",
        "pricing.manage",
        "passes.manage",
        "store.manage",
        "games.manage",
        "tournaments.manage",
        "cafe.switch",
    ],
    "staff": [
        "dashboard.view",
        "booking.manage",
        "gaming.manage",
        "gamers.view",
        "store.manage",
        "games.manage",
    ],
}

VALID_ROLES = set(DEFAULT_ROLE_PERMISSIONS.keys())


def _normalize_matrix(data: Optional[Dict[str, List[str]]] = None) -> Dict[str, List[str]]:
    matrix = {
        "owner": list(DEFAULT_ROLE_PERMISSIONS["owner"]),
        "manager": list(DEFAULT_ROLE_PERMISSIONS["manager"]),
        "staff": list(DEFAULT_ROLE_PERMISSIONS["staff"]),
    }

    if not data:
        return matrix

    for role, perms in data.items():
        if role not in VALID_ROLES:
            continue
        clean = [p for p in set(perms or []) if p in ALL_PERMISSIONS]
        matrix[role] = clean

    if not matrix["owner"]:
        matrix["owner"] = list(DEFAULT_ROLE_PERMISSIONS["owner"])
    return matrix


def get_role_permissions(vendor_id: int) -> Dict[str, List[str]]:
    rows = VendorRolePermission.query.filter_by(vendor_id=vendor_id).all()
    if not rows:
        return _normalize_matrix()

    grouped = {"owner": [], "manager": [], "staff": []}
    for row in rows:
        if row.role in grouped and row.permission in ALL_PERMISSIONS:
            grouped[row.role].append(row.permission)

    return _normalize_matrix(grouped)


def set_role_permissions(vendor_id: int, matrix: Dict[str, List[str]]) -> Dict[str, List[str]]:
    normalized = _normalize_matrix(matrix)

    VendorRolePermission.query.filter_by(vendor_id=vendor_id).delete(synchronize_session=False)
    for role, perms in normalized.items():
        for perm in perms:
            db.session.add(VendorRolePermission(vendor_id=vendor_id, role=role, permission=perm))
    db.session.commit()

    return normalized


def reset_role_permissions(vendor_id: int) -> Dict[str, List[str]]:
    VendorRolePermission.query.filter_by(vendor_id=vendor_id).delete(synchronize_session=False)
    db.session.commit()
    return _normalize_matrix()


def generate_unique_pin(vendor_id: int) -> str:
    active_staff = VendorStaff.query.filter_by(vendor_id=vendor_id).all()

    # Compare by checking hash for candidate instead of storing raw pins.
    for _ in range(200):
        candidate = str(random.randint(1000, 9999))
        if all(not check_password_hash(s.pin_hash, candidate) for s in active_staff):
            return candidate

    for _ in range(200):
        candidate = str(random.randint(100000, 999999))
        if all(not check_password_hash(s.pin_hash, candidate) for s in active_staff):
            return candidate

    return str(random.randint(100000, 999999))


def create_staff(vendor_id: int, name: str, role: str) -> dict:
    if role not in VALID_ROLES or role == "owner":
        raise ValueError("role must be manager or staff")

    pin = generate_unique_pin(vendor_id)
    staff = VendorStaff(
        vendor_id=vendor_id,
        name=name.strip(),
        role=role,
        pin_hash=generate_password_hash(pin),
        is_active=True,
    )
    db.session.add(staff)
    db.session.commit()

    payload = staff.to_dict()
    payload["generated_pin"] = pin
    return payload


def verify_staff_pin(vendor_id: int, pin: str) -> Optional[VendorStaff]:
    staff = VendorStaff.query.filter_by(vendor_id=vendor_id, is_active=True).all()
    for member in staff:
        if check_password_hash(member.pin_hash, pin):
            return member
    return None


def create_access_token_payload(vendor_id: int, staff_id: str, name: str, role: str) -> dict:
    role_matrix = get_role_permissions(vendor_id)
    permissions = role_matrix.get(role, [])

    token = create_access_token(
        identity=str(staff_id),
        additional_claims={
            "scope": "vendor_access",
            "vendor_id": vendor_id,
            "staff": {
                "id": str(staff_id),
                "name": name,
                "role": role,
                "permissions": permissions,
            },
        },
    )

    return {
        "token": token,
        "vendor_id": vendor_id,
        "staff": {
            "id": str(staff_id),
            "name": name,
            "role": role,
            "permissions": permissions,
        },
    }


def claim_vendor_id(claims: dict) -> Optional[int]:
    if not claims:
        return None

    if claims.get("vendor_id") is not None:
        try:
            return int(claims["vendor_id"])
        except (TypeError, ValueError):
            pass

    vendor = claims.get("vendor")
    if isinstance(vendor, dict) and vendor.get("id") is not None:
        try:
            return int(vendor["id"])
        except (TypeError, ValueError):
            pass

    sub = claims.get("sub")
    if isinstance(sub, dict) and sub.get("id") is not None:
        try:
            return int(sub["id"])
        except (TypeError, ValueError):
            pass

    return None


def claims_permissions(claims: dict, vendor_id: int) -> List[str]:
    if not claims:
        return []

    scope = claims.get("scope")
    if scope == "vendor_access":
        staff = claims.get("staff") or {}
        perms = staff.get("permissions") or []
        return [p for p in perms if p in ALL_PERMISSIONS]

    # Backward compatibility: owner login token can act as full access for matching vendor.
    claim_vid = claim_vendor_id(claims)
    if claim_vid == vendor_id:
        return list(DEFAULT_ROLE_PERMISSIONS["owner"])

    return []
