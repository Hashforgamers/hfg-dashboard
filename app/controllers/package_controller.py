import os

from flask import Blueprint, jsonify, current_app, request
from app.models.package import Package
from app.services.subscription_service import get_package_price


bp_packages = Blueprint('packages', __name__)


def _extract_admin_key() -> str:
    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return (request.headers.get("x-admin-key") or "").strip()


def _admin_authorized() -> bool:
    expected = (os.getenv("SUPER_ADMIN_API_KEY") or "").strip()
    if not expected:
        return True
    return _extract_admin_key() == expected


def _serialize_package(pkg: Package) -> dict:
    features = pkg.features or {}
    return {
        "id": pkg.id,
        "code": pkg.code,
        "name": pkg.name,
        "pc_limit": pkg.pc_limit,
        "active": bool(pkg.active),
        "is_custom": bool(pkg.is_custom),
        "monthly": float(features.get("price_inr", 0) or 0),
        "quarterly": float(features.get("quarterly_price_inr", 0) or 0),
        "yearly": float(features.get("yearly_price_inr", 0) or 0),
        "onboarding_offer": features.get("onboarding_offer"),
        "plan_features": features.get("plan_features") or [],
        "features": features,
    }


@bp_packages.get('/', strict_slashes=False)
def list_packages():
    """
    Get all active packages with prices
    In dev mode, shows test prices
    """
    packages = Package.query.filter_by(active=True).order_by(Package.id).all()
    
    dev_mode = current_app.config.get('SUBSCRIPTION_DEV_MODE', False)
    
    result = []
    for pkg in packages:
        # ✅ Use the service function for consistency
        try:
            price = get_package_price(pkg.code)
        except ValueError:
            # Fallback for packages without price
            price = 0.0
        
        result.append({
            "id": pkg.id,
            "code": pkg.code,
            "name": pkg.name,
            "pc_limit": pkg.pc_limit,
            "price": price,
            "original_price": float(pkg.features.get('price_inr', 0)),
            "is_custom": pkg.is_custom,
            "is_free": price == 0,
            "features": pkg.features,
            "description": f"Manage up to {pkg.pc_limit} PCs/Consoles"
        })
    
    return jsonify({
        "packages": result,
        "dev_mode": dev_mode,
        "test_price": current_app.config.get('SUBSCRIPTION_TEST_PRICE', 1) if dev_mode else None
    }), 200


@bp_packages.get('/<package_code>', strict_slashes=False)
def get_package(package_code):
    """Get single package details"""
    package = Package.query.filter_by(code=package_code, active=True).first_or_404()
    
    dev_mode = current_app.config.get('SUBSCRIPTION_DEV_MODE', False)
    
    # ✅ Use the service function
    try:
        price = get_package_price(package_code)
    except ValueError:
        price = 0.0
    
    return jsonify({
        "id": package.id,
        "code": package.code,
        "name": package.name,
        "pc_limit": package.pc_limit,
        "price": price,
        "original_price": float(package.features.get('price_inr', 0)),
        "is_custom": package.is_custom,
        "is_free": price == 0,
        "features": package.features,
        "dev_mode": dev_mode
    }), 200


@bp_packages.get('/admin/catalog', strict_slashes=False)
def admin_catalog():
    if not _admin_authorized():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    packages = Package.query.order_by(Package.id.asc()).all()
    return jsonify({"success": True, "models": [_serialize_package(pkg) for pkg in packages]}), 200


@bp_packages.put('/admin/catalog', strict_slashes=False)
def upsert_admin_catalog():
    if not _admin_authorized():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    models = payload.get("models") or []
    if not isinstance(models, list) or not models:
        return jsonify({"success": False, "message": "models must be a non-empty list"}), 400

    changed = 0
    for item in models:
        if not isinstance(item, dict):
            continue
        code = (item.get("code") or "").strip().lower()
        name = (item.get("name") or "").strip()
        if not code or not name:
            continue

        package = Package.query.filter_by(code=code).first()
        if not package:
            package = Package(code=code, name=name, pc_limit=0, is_custom=False, features={}, active=True)
            from app.extension.extensions import db
            db.session.add(package)

        package.name = name
        package.pc_limit = max(0, int(item.get("pc_limit") or 0))
        package.active = bool(item.get("enabled", item.get("active", True)))

        existing_features = dict(package.features or {})
        existing_features.update(
            {
                "price_inr": float(item.get("monthly") or existing_features.get("price_inr") or 0),
                "quarterly_price_inr": float(item.get("quarterly") or existing_features.get("quarterly_price_inr") or 0),
                "yearly_price_inr": float(item.get("yearly") or existing_features.get("yearly_price_inr") or 0),
                "onboarding_offer": item.get("onboarding_offer"),
                "plan_features": item.get("features") or item.get("plan_features") or [],
            }
        )
        package.features = existing_features
        changed += 1

    from app.extension.extensions import db
    db.session.commit()

    packages = Package.query.order_by(Package.id.asc()).all()
    return jsonify({"success": True, "updated": changed, "models": [_serialize_package(pkg) for pkg in packages]}), 200
