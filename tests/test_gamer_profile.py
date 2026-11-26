"""Exercise the production gamer-profile handler against isolated SQL storage."""
import ast
from datetime import date, time, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import pytest
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def api():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    db = SQLAlchemy(app)

    class Contact(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        phone = db.Column(db.String(20)); email = db.Column(db.String(80))

    class User(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(80)); game_username = db.Column(db.String(80)); avatar_path = db.Column(db.String(80))
        contact_id = db.Column(db.Integer, db.ForeignKey(Contact.id))
        contact_info = db.relationship(Contact)

    class Slot(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        start_time = db.Column(db.Time); end_time = db.Column(db.Time)

    class AvailableGame(db.Model):
        id = db.Column(db.Integer, primary_key=True); game_name = db.Column(db.String(40))

    class Booking(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        slot_id = db.Column(db.Integer); game_id = db.Column(db.Integer); status = db.Column(db.String(20))

    class Transaction(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        vendor_id = db.Column(db.Integer); user_id = db.Column(db.Integer); booking_id = db.Column(db.Integer)
        booked_date = db.Column(db.Date); booking_time = db.Column(db.Time)
        amount = db.Column(db.Float); meals_amount = db.Column(db.Float, default=0)
        mode_of_payment = db.Column(db.String(20)); booking_type = db.Column(db.String(20), default='booking')
        source_channel = db.Column(db.String(20), default='app'); settlement_status = db.Column(db.String(20), default='pending')
        initiated_by_staff_name = db.Column(db.String(40))

    route = next(n for n in ast.parse((ROOT / 'app/routes.py').read_text()).body
                 if isinstance(n, ast.FunctionDef) and n.name == 'get_gamer_profile')
    route.decorator_list = []
    scope = dict(db=db, User=User, Slot=Slot, AvailableGame=AvailableGame, Booking=Booking, Transaction=Transaction,
                 jsonify=jsonify, text=text, current_app=app, datetime=datetime, date=date, timedelta=timedelta)
    exec(compile(ast.Module(body=[route], type_ignores=[]), 'routes.py', 'exec'), scope)
    app.add_url_rule('/vendor/<int:vendor_id>/knowYourGamer/<int:user_id>', view_func=scope['get_gamer_profile'])
    with app.app_context():
        db.create_all()
        db.session.add_all([
            Contact(id=1, phone='9999999999', email='g@example.test'),
            User(id=2001, name='Riya', game_username='riya', contact_id=1),
            Slot(id=1, start_time=time(23, 0), end_time=time(0, 0)),
            Slot(id=2, start_time=time(10, 0), end_time=time(10, 30)),
            AvailableGame(id=1, game_name='PS5'), AvailableGame(id=2, game_name='PC'),
            Booking(id=1, slot_id=1, game_id=1, status='completed'),
            Booking(id=2, slot_id=2, game_id=1, status='completed'),
            Booking(id=3, slot_id=2, game_id=2, status='cancelled'),
            Transaction(id=1, vendor_id=1, user_id=2001, booking_id=1, booked_date=date(2026, 11, 1), booking_time=time(9), amount=200, mode_of_payment='cash'),
            Transaction(id=2, vendor_id=1, user_id=2001, booking_id=2, booked_date=date(2026, 11, 20), booking_time=time(9), amount=100, mode_of_payment='upi'),
            Transaction(id=3, vendor_id=1, user_id=2001, booking_id=3, booked_date=date(2026, 11, 20), booking_time=time(8), amount=50, mode_of_payment='upi'),
            Transaction(id=4, vendor_id=2, user_id=2001, booking_id=1, booked_date=date(2026, 11, 2), booking_time=time(9), amount=999, mode_of_payment='cash'),
        ])
        db.session.commit()
        yield SimpleNamespace(client=app.test_client())


def test_profile_returns_cafe_scoped_history_newest_first(api):
    res = api.client.get('/vendor/1/knowYourGamer/2001')
    assert res.status_code == 200, res.json
    body = res.json
    assert body['name'] == 'Riya' and body['phone'] == '9999999999'
    assert [h['transaction_id'] for h in body['history']] == [2, 3, 1]
    overnight = body['history'][-1]
    assert overnight['start_time'] == '23:00' and overnight['duration_minutes'] == 60
    s = body['summary']
    assert s['sessions'] == 3 and s['visits'] == 2
    assert s['total_amount'] == 350 and s['hours_played'] == 2.0
    assert s['favourite_console'] == 'PS5'
    assert s['first_visit'] == '2026-11-01' and s['last_visit'] == '2026-11-20'


def test_profile_hides_gamers_without_history_at_this_cafe(api):
    assert api.client.get('/vendor/3/knowYourGamer/2001').status_code == 404
    assert api.client.get('/vendor/1/knowYourGamer/1').status_code == 404
