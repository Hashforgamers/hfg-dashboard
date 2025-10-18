from app.models.package import Package
from app.extension.extensions import db

def list_packages(active_only=True):
    q = Package.query
    if active_only:
        q = q.filter_by(active=True)
    return q.order_by(Package.pc_limit.asc()).all()

def create_package(data):
    pkg = Package(
        code=data['code'],
        name=data['name'],
        pc_limit=data['pc_limit'],
        is_custom=data.get('is_custom', False),
        features=data.get('features') or {},
        active=True
    )
    db.session.add(pkg)
    db.session.commit()
    return pkg

def update_package(pkg_id, data):
    pkg = Package.query.get_or_404(pkg_id)
    if 'name' in data: pkg.name = data['name']
    if 'pc_limit' in data: pkg.pc_limit = int(data['pc_limit'])
    if 'features' in data: pkg.features = data['features']
    if 'active' in data: pkg.active = bool(data['active'])
    db.session.commit()
    return pkg
