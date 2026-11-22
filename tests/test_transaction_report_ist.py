"""Transactions page: IST day boundaries and desk money from the cafe wallet ledger."""
import ast
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
NAMES = {'_transaction_local_stamp', '_cafe_wallet_report_rows', 'CAFE_LEDGER_REPORT_KINDS'}


def helpers(**scope):
    tree = ast.parse((ROOT / 'app/routes.py').read_text())
    body = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in NAMES)
            or (isinstance(n, ast.Assign) and any(getattr(t, 'id', None) in NAMES for t in n.targets))]
    scope.update(datetime=datetime, timedelta=timedelta, dt_timezone=timezone, IST=ZoneInfo('Asia/Kolkata'))
    exec(compile(ast.Module(body=body, type_ignores=[]), 'routes', 'exec'), scope)
    return scope


def test_early_morning_utc_payment_lands_on_ist_day():
    h = helpers()
    txn = SimpleNamespace(booking_date=date(2026, 11, 21), booking_time=time(22, 58), source_channel='dashboard')
    assert h['_transaction_local_stamp'](txn) == datetime(2026, 11, 22, 4, 28)


def test_excel_history_rows_are_already_local():
    h = helpers()
    txn = SimpleNamespace(booking_date=date(2026, 3, 1), booking_time=time(23, 0), source_channel='excel_import')
    assert h['_transaction_local_stamp'](txn) == datetime(2026, 3, 1, 23, 0)


URL = os.getenv('CAFE_TEST_DATABASE_URL', '')


@pytest.mark.skipif(not URL.startswith('postgresql'), reason='needs PostgreSQL')
def test_wallet_desk_money_is_listed_once_in_ist_range():
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy
    from sqlalchemy import text
    import uuid
    app = Flask(__name__)
    schema = 'report_' + uuid.uuid4().hex
    app.config.update(SQLALCHEMY_DATABASE_URI=URL,
                      SQLALCHEMY_ENGINE_OPTIONS={'connect_args': {'options': f'-csearch_path={schema}'}})
    db = SQLAlchemy(app)

    class User(db.Model):
        __tablename__ = 'users'
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)

    class CafeLedger(db.Model):
        __tablename__ = 'cafe_wallet_ledger'
        id = db.Column(db.Integer, primary_key=True)
        vendor_id = db.Column(db.Integer); user_id = db.Column(db.Integer); kind = db.Column(db.String)
        amount = db.Column(db.BigInteger); method = db.Column(db.String); actor_id = db.Column(db.String)
        actor_name = db.Column(db.String); reason = db.Column(db.String); created_at = db.Column(db.DateTime)

    import sys, types
    module = types.ModuleType('app.models.cafe_wallet'); module.CafeLedger = CafeLedger
    sys.modules['app.models.cafe_wallet'] = module
    try:
        with app.app_context():
            db.session.execute(text(f'CREATE SCHEMA {schema}')); db.session.commit()
            db.create_all()
            db.session.add(User(id=1, name='Harsh'))
            stamp = datetime(2026, 11, 21, 22, 58)  # 04:28 IST on the 22nd
            for i, (kind, amount) in enumerate([('topup', 50000), ('session_collection', 2500), ('capture', -3000),
                                                 ('extension_capture', -100), ('reserve', 0)]):
                db.session.add(CafeLedger(id=i + 1, vendor_id=7, user_id=1, kind=kind, amount=amount, method='cash',
                                          actor_id='s1', actor_name='Desk', reason='r', created_at=stamp))
            db.session.commit()
            h = helpers(db=db, User=User, text=text)
            rows = h['_cafe_wallet_report_rows'](7, date(2026, 11, 22), date(2026, 11, 22))
            assert sorted((r['bookingType'], r['amount']) for r in rows) == [('extra_time_collection', 25.0), ('wallet_topup', 500.0)]
            assert {r['slotDate'] for r in rows} == {'2026-11-22'} and rows[0]['slotTime'] == '04:28 AM'
            assert h['_cafe_wallet_report_rows'](7, date(2026, 11, 21), date(2026, 11, 21)) == []
    finally:
        sys.modules.pop('app.models.cafe_wallet', None)
        with app.app_context():
            db.session.rollback(); db.session.execute(text(f'DROP SCHEMA {schema} CASCADE')); db.session.commit()
