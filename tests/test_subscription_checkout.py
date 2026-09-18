"""Isolated checkout tests with real subscription rows and provider responses."""
import sys
from pathlib import Path
from unittest.mock import Mock
import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.controllers import subscription_controller as routes
from app.extension.extensions import db
from app.models.extraServiceCategory import ExtraServiceCategory
from app.models.user import User
from app.models.uploadedImage import Image
from app.models.booking import Booking
from app.models.slot import Slot
from app.models.bookingExtraService import BookingExtraService
from app.models.bookingSquadMember import BookingSquadMember
from app.models.extraServiceMenu import ExtraServiceMenu
from app.models.extraServiceMenuImage import ExtraServiceMenuImage
from app.models.console import Console
from app.models.hardwareSpecification import HardwareSpecification
from app.models.maintenanceStatus import MaintenanceStatus
from app.models.priceAndCost import PriceAndCost
from app.models.additionalDetails import AdditionalDetails
from app.models.vendorGame import VendorGame
from app.models.game import Game
from app.models.package import Package
from app.models.subscription import Subscription

@pytest.fixture
def app(monkeypatch):
    app = Flask(__name__)
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://', RAZORPAY_KEY_ID='rzp_test_local')
    db.init_app(app)
    app.register_blueprint(routes.bp_subs, url_prefix='/api/vendors/<int:vendor_id>/subscription')
    with app.app_context():
        db.metadata.create_all(db.engine, tables=[Package.__table__, Subscription.__table__])
        db.session.add(Package(code='base', name='Base', pc_limit=5, features={'price_inr': 100}, active=True))
        db.session.commit()
        monkeypatch.setattr(routes, 'verify_payment_signature', Mock(return_value=True))
        monkeypatch.setattr(routes, 'get_order_details', Mock(return_value=order()))
        monkeypatch.setattr(routes, 'get_payment_details', Mock(return_value=payment()))
        monkeypatch.setattr(routes, 'create_order', Mock(return_value={'id': 'order_test'}))
        yield app
        db.session.remove()
        db.metadata.drop_all(db.engine, tables=[Subscription.__table__, Package.__table__])

def order():
    return dict(id='order_test', amount=10000, currency='INR', notes=dict(vendor_id='1', package_code='base', action='new', billing_cycle='monthly'))

def payment():
    return dict(id='pay_test', order_id='order_test', amount=10000, currency='INR', status='captured')

def verify(app, **changes):
    payload = dict(razorpay_order_id='order_test', razorpay_payment_id='pay_test', razorpay_signature='sig', package_code='base', action='new')
    payload.update(changes)
    return app.test_client().post('/api/vendors/1/subscription/verify-payment', json=payload)

def test_first_purchase_unlocks_and_duplicate_is_idempotent(app):
    client = app.test_client()
    assert client.get('/api/vendors/1/subscription/status').json['locked'] is True
    result = client.post('/api/vendors/1/subscription/create-order', json={'package_code': 'base'})
    assert result.status_code == 200, result.json
    assert routes.create_order.call_args.kwargs['notes']['vendor_id'] == '1'
    response = verify(app)
    assert response.status_code == 200, response.json
    assert client.get('/api/vendors/1/subscription/status').json['is_active'] is True
    assert verify(app).status_code == 200
    assert Subscription.query.count() == 1

@pytest.mark.parametrize('case', ['other_cafe', 'wrong_package', 'missing_link', 'uncaptured', 'wrong_currency', 'underpayment', 'invalid_signature'])
def test_rejects_invalid_payment(app, case):
    order_data, payment_data = order(), payment()
    if case == 'other_cafe': order_data['notes']['vendor_id'] = '2'
    if case == 'wrong_package': order_data['notes']['package_code'] = 'elite'
    if case == 'missing_link': payment_data.pop('order_id')
    if case == 'uncaptured': payment_data['status'] = 'authorized'
    if case == 'wrong_currency': payment_data['currency'] = 'USD'
    if case == 'underpayment': payment_data['amount'] = 9999
    if case == 'invalid_signature': routes.verify_payment_signature.return_value = False
    routes.get_order_details.return_value = order_data
    routes.get_payment_details.return_value = payment_data
    assert verify(app).status_code == 400
    assert Subscription.query.count() == 0

def test_polled_payment_uses_provider_verification(app):
    assert verify(app, razorpay_signature='polled_payment').status_code == 200
    routes.verify_payment_signature.assert_not_called()
    routes.get_payment_details.assert_called_once_with('pay_test')

def test_request_cannot_change_order_action(app):
    assert verify(app, action='renew').status_code == 200
    assert Subscription.query.count() == 1
