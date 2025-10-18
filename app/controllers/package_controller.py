from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.services.package_service import list_packages, create_package, update_package

bp_packages = Blueprint('packages', __name__, url_prefix='/api/packages')

@bp_packages.get('/')
def get_packages():
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    pkgs = list_packages(active_only=active_only)
    return jsonify([{
        "id": p.id, "code": p.code, "name": p.name, "pc_limit": p.pc_limit, "active": p.active, "features": p.features
    } for p in pkgs]), 200

@bp_packages.post('/')
def post_package():
    data = request.get_json()
    pkg = create_package(data)
    return jsonify({"id": pkg.id}), 201

@bp_packages.patch('/<int:pkg_id>')
def patch_package(pkg_id):
    data = request.get_json()
    pkg = update_package(pkg_id, data)
    return jsonify({"id": pkg.id, "active": pkg.active}), 200
