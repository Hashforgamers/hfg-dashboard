"""Isolated checkout tests with real subscription rows and provider responses."""
import sys
import os
import uuid
from sqlalchemy import create_engine, text, MetaData, ForeignKeyConstraint
from pathlib import Path
from unittest.mock import Mock
import pytest
from flask import Flask
import jwt
from datetime import datetime, timezone, timedelta

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
from app.models.vendor import Vendor
from app.models.console_link_session import ConsoleLinkSession
from app.models.subscription_checkout import SubscriptionCheckout

@pytest.fixture
def app(monkeypatch,request):
    app = Flask(__name__)
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://', RAZORPAY_KEY_ID='rzp_test_local', JWT_SECRET_KEY='test-secret-for-subscriptions-1234567890')
    database_url=os.environ.get('SUBSCRIPTION_TEST_DATABASE_URL')
    schema='subscription_test_'+uuid.uuid4().hex[:12]
    admin=None
    if database_url:
        admin=create_engine(database_url)
        with admin.begin() as connection: connection.execute(text('CREATE SCHEMA '+schema))
        def cleanup_schema():
            with admin.begin() as connection:connection.execute(text('DROP SCHEMA IF EXISTS '+schema+' CASCADE'))
            admin.dispose()
        request.addfinalizer(cleanup_schema)
        app.config['SQLALCHEMY_DATABASE_URI']=database_url
        app.config['SQLALCHEMY_ENGINE_OPTIONS']={'connect_args':{'options':'-csearch_path='+schema}}
    db.init_app(app)
    app.register_blueprint(routes.bp_subs, url_prefix='/api/vendors/<int:vendor_id>/subscription')
    with app.app_context():
        if database_url:
            # Keep production columns/indexes; omit unrelated FK dependencies in this isolated schema.
            metadata=MetaData()
            selected=[Vendor,Package,Subscription,Console,ConsoleLinkSession,SubscriptionCheckout]
            for model in selected:
                table=model.__table__.to_metadata(metadata)
                for constraint in list(table.constraints):
                    if isinstance(constraint,ForeignKeyConstraint):table.constraints.remove(constraint)
                table.foreign_keys.clear()
                for column in table.columns:column.foreign_keys.clear()
            metadata.create_all(db.engine)
        else:
            db.metadata.create_all(db.engine, tables=[Vendor.__table__,Package.__table__, Subscription.__table__])
        db.session.add(Vendor(id=1,cafe_name='<Cafe>',owner_name='Owner',timing_id=1))
        db.session.add(Package(code='base', name='Base', pc_limit=5, features={'price_inr': 100}, active=True))
        db.session.commit()
        monkeypatch.setattr(routes, 'verify_payment_signature', Mock(return_value=True))
        monkeypatch.setattr(routes, 'get_order_details', Mock(return_value=order()))
        monkeypatch.setattr(routes, 'get_payment_details', Mock(return_value=payment()))
        monkeypatch.setattr(routes, 'create_order', Mock(return_value={'id': 'order_test'}))
        yield app
        db.session.remove()
        if database_url:
            db.engine.dispose()
            with admin.begin() as connection:connection.execute(text('DROP SCHEMA '+schema+' CASCADE'))
            admin.dispose()
        else:
            db.metadata.drop_all(db.engine, tables=[Subscription.__table__, Package.__table__,Vendor.__table__])

def order():
    return dict(id='order_test', amount=10000, currency='INR', notes=dict(vendor_id='1', package_code='base', action='new', billing_cycle='monthly'))

def payment():
    return dict(id='pay_test', order_id='order_test', amount=10000, currency='INR', status='captured')

def verify(app, **changes):
    payload = dict(razorpay_order_id='order_test', razorpay_payment_id='pay_test', razorpay_signature='sig', package_code='base', action='new')
    payload.update(changes)
    return app.test_client().post('/api/vendors/1/subscription/verify-payment', json=payload, headers=auth(app))

def test_first_purchase_unlocks_and_duplicate_is_idempotent(app):
    client = app.test_client()
    assert client.get('/api/vendors/1/subscription/status',headers=auth(app)).json['locked'] is True
    result = client.post('/api/vendors/1/subscription/create-order', json={'package_code': 'base'},headers=auth(app))
    assert result.status_code == 409  # New purchases must first accept an invoice preview.
    response = verify(app)
    assert response.status_code == 200, response.json
    assert client.get('/api/vendors/1/subscription/status',headers=auth(app)).json['is_active'] is True
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


def auth(app,vendor_id=1):
    token=jwt.encode({'sub':{'type':'vendor','id':vendor_id},'exp':datetime.now(timezone.utc)+timedelta(hours=1)},app.config['JWT_SECRET_KEY'],algorithm='HS256')
    return {'Authorization':'Bearer '+token}
