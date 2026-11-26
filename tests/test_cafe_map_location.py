"""Settings can correct the cafe's map location captured at onboarding."""
import ast
from pathlib import Path
from types import SimpleNamespace
import pytest
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def api():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    db = SQLAlchemy(app)

    class PhysicalAddress(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        vendor_id = db.Column(db.Integer)
        addressLine1 = db.Column(db.String(255)); pincode = db.Column(db.String(10))
        state = db.Column(db.String(100)); country = db.Column(db.String(100))
        latitude = db.Column(db.String(20)); longitude = db.Column(db.String(20))

    class Vendor(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        cafe_name = db.Column(db.String(255)); display_name = db.Column(db.String(120))
        address_id = db.Column(db.Integer, db.ForeignKey(PhysicalAddress.id))
        physical_address = db.relationship(PhysicalAddress)
        contact_info = website = None
        public_name = property(lambda self: self.display_name or self.cafe_name)

    route = next(n for n in ast.parse((ROOT / 'app/routes.py').read_text()).body
                 if isinstance(n, ast.FunctionDef) and n.name == 'update_business_details')
    route.decorator_list = []
    scope = dict(db=db, Vendor=Vendor, PhysicalAddress=PhysicalAddress, request=request, jsonify=jsonify,
                 SQLAlchemyError=SQLAlchemyError, current_app=app, _invalidate_vendor_caches=lambda vid: None)
    exec(compile(ast.Module(body=[route], type_ignores=[]), 'routes.py', 'exec'), scope)
    app.add_url_rule('/vendor/<int:vendor_id>/business-details', view_func=scope['update_business_details'], methods=['PATCH'])
    with app.app_context():
        db.create_all()
        addr = PhysicalAddress(id=1, addressLine1='MG Road', pincode='560001', state='KA', country='India', latitude='0', longitude='0')
        db.session.add_all([addr, Vendor(id=1, cafe_name='Cafe', address_id=1), Vendor(id=2, cafe_name='No address')])
        db.session.commit()
        yield SimpleNamespace(client=app.test_client(), db=db, PhysicalAddress=PhysicalAddress)


def test_location_update_saves_normalised_coordinates(api):
    res = api.client.patch('/vendor/1/business-details', json={'latitude': '12.9716', 'longitude': 77.5946})
    assert res.status_code == 200, res.json
    assert res.json['data']['address']['latitude'] == '12.971600'
    row = api.db.session.get(api.PhysicalAddress, 1)
    assert (row.latitude, row.longitude) == ('12.971600', '77.594600')


@pytest.mark.parametrize('body', [{'latitude': 12.9}, {'latitude': 91, 'longitude': 0}, {'latitude': 'x', 'longitude': 1}, {'latitude': 0, 'longitude': 0}])
def test_invalid_location_is_rejected_without_change(api, body):
    assert api.client.patch('/vendor/1/business-details', json=body).status_code == 400
    assert api.db.session.get(api.PhysicalAddress, 1).latitude == '0'


def test_location_needs_an_address(api):
    assert api.client.patch('/vendor/2/business-details', json={'latitude': 12.9, 'longitude': 77.5}).status_code == 400
