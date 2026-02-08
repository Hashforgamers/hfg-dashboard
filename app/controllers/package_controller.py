from flask import Blueprint, jsonify, current_app
from app.models.package import Package
from app.services.subscription_service import get_package_price

bp_packages = Blueprint('packages', __name__, url_prefix='/api/packages')


@bp_packages.get('/')
def list_packages():
    """
    Get all active packages with prices
    In dev mode, shows test prices
    """
    packages = Package.query.filter_by(active=True).order_by(Package.id).all()
    
    dev_mode = current_app.config.get('SUBSCRIPTION_DEV_MODE', False)
    
    result = []
    for pkg in packages:
        # Get actual or test price
        if dev_mode:
            price = current_app.config.get('SUBSCRIPTION_TEST_PRICE', 1) if pkg.code != 'early_onboard' else 0
        else:
            price = float(pkg.features.get('price_inr', 0))
        
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


@bp_packages.get('/<package_code>')
def get_package(package_code):
    """Get single package details"""
    package = Package.query.filter_by(code=package_code, active=True).first_or_404()
    
    dev_mode = current_app.config.get('SUBSCRIPTION_DEV_MODE', False)
    
    if dev_mode and package.code != 'early_onboard':
        price = current_app.config.get('SUBSCRIPTION_TEST_PRICE', 1)
    else:
        price = float(package.features.get('price_inr', 0))
    
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
