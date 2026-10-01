import os
import hmac
import re

from flask import Blueprint, jsonify, current_app, request
from app.models.package import Package
from app.models.subscription import Subscription
from app.services.subscription_service import get_package_price
from app.services.subscription_commerce import FEATURES
from app.services.pricing_math import money
from app.extension.extensions import db


bp_packages = Blueprint('packages', __name__)


def _extract_admin_key() -> str:
    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return (request.headers.get("x-admin-key") or "").strip()


def _admin_authorized() -> bool:
    expected = (os.getenv("SUPER_ADMIN_API_KEY") or "").strip()
    return bool(expected) and hmac.compare_digest(_extract_admin_key(), expected)


def _serialize_package(pkg: Package) -> dict:
    features = pkg.features or {}
    plan_features = features.get("plan_features") or []
    return {
        "id": pkg.id,
        "code": pkg.code,
        "name": pkg.name,
        "pc_limit": pkg.pc_limit,
        "active": bool(pkg.active),
        "enabled": bool(pkg.active),
        "is_custom": bool(pkg.is_custom),
        "monthly": float(features.get("price_inr", 0) or 0),
        "quarterly": float(features.get("quarterly_price_inr", 0) or 0),
        "yearly": float(features.get("yearly_price_inr", 0) or 0),
        "onboarding_offer": features.get("onboarding_offer"),
        "plan_features": plan_features,
        "features": plan_features,
        "raw_features": features,
        "entitlements": features.get("entitlements", list(FEATURES)),
        "extra_pc_monthly": features.get("extra_pc_monthly", 0),
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
            "features": dict(pkg.features or {}, entitlements=(pkg.features or {}).get("entitlements",list(FEATURES))),
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
    if not isinstance(payload, dict):
        return jsonify(success=False,message="Supply a JSON object"),400
    models = payload.get("models") or []
    if not isinstance(models, list) or not models:
        return jsonify({"success": False, "message": "models must be a non-empty list"}), 400

    changed = 0
    try:
        seen=set()
        for item in models:
            if not isinstance(item, dict): raise ValueError('Each plan must be an object')
            code=str(item.get('code','')).strip().lower();name=str(item.get('name','')).strip()
            if not re.fullmatch(r'[a-z0-9_-]{1,32}',code) or not 1 <= len(name) <= 64:
                raise ValueError('Use a valid plan code and name up to 64 characters')
            if code in seen: raise ValueError('Duplicate plan code')
            seen.add(code)
            limit=item.get('pc_limit')
            if type(limit) is not int or not 0 <= limit <= 10000: raise ValueError('PC limit must be a whole number from 0 to 10000')
            enabled=item.get('enabled',item.get('active',True))
            if type(enabled) is not bool: raise ValueError('Plan status must be boolean')
            package=Package.query.filter_by(code=code).with_for_update().first()
            if not package:
                package=Package(code=code,name=name,pc_limit=limit,is_custom=True,features={},active=enabled)
                db.session.add(package)
            f=dict(package.features or {})
            for incoming,stored in [('monthly','price_inr'),('quarterly','quarterly_price_inr'),('yearly','yearly_price_inr'),('extra_pc_monthly','extra_pc_monthly')]:
                if incoming in item: f[stored]=float(money(item[incoming]))
            descriptions=item.get('features',item.get('plan_features',f.get('plan_features',[])))
            if not isinstance(descriptions,list) or len(descriptions)>50 or any(not isinstance(v,str) or len(v)>200 for v in descriptions):
                raise ValueError('Features must be up to 50 short descriptions')
            entitlements=item.get('entitlements',f.get('entitlements',list(FEATURES)))
            if not isinstance(entitlements,list) or any(not isinstance(v,str) or v not in FEATURES for v in entitlements):
                raise ValueError('Unknown dashboard feature')
            f.update(plan_features=descriptions,entitlements=sorted(set(entitlements)))
            if 'onboarding_offer' in item: f['onboarding_offer']=item['onboarding_offer']
            package.name=name;package.pc_limit=limit;package.active=enabled;package.features=f
            changed+=1
        db.session.commit()
    except (ValueError,TypeError) as error:
        db.session.rollback()
        return jsonify(success=False,message=str(error)),400

    packages = Package.query.order_by(Package.id.asc()).all()
    return jsonify({"success": True, "updated": changed, "models": [_serialize_package(pkg) for pkg in packages]}), 200


@bp_packages.delete('/admin/catalog/<package_code>', strict_slashes=False)
def delete_admin_catalog_item(package_code):
    if not _admin_authorized():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    code = (package_code or "").strip().lower()
    if not code:
        return jsonify({"success": False, "message": "package code is required"}), 400

    from app.extension.extensions import db

    package = Package.query.filter_by(code=code).first()
    if not package:
        return jsonify({"success": False, "message": "Plan not found"}), 404

    subscription_count = Subscription.query.filter_by(package_id=package.id).count()
    if subscription_count:
        package.active = False
        db.session.commit()
        packages = Package.query.order_by(Package.id.asc()).all()
        return jsonify({
            "success": True,
            "deleted": False,
            "deactivated": True,
            "message": "Plan has subscription history, so it was marked inactive.",
            "models": [_serialize_package(pkg) for pkg in packages],
        }), 200

    db.session.delete(package)
    db.session.commit()
    packages = Package.query.order_by(Package.id.asc()).all()
    return jsonify({
        "success": True,
        "deleted": True,
        "deactivated": False,
        "models": [_serialize_package(pkg) for pkg in packages],
    }), 200
