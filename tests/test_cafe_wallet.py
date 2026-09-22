"""Real transactional integration tests. Set CAFE_TEST_DATABASE_URL to a disposable PostgreSQL DB."""
import importlib.util
import os
from pathlib import Path
import sys
import types
import uuid
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, decode_token
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import jwt

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def env(monkeypatch):
    url = os.getenv('CAFE_TEST_DATABASE_URL', 'sqlite://')
    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI=url, SECRET_KEY='test-secret-'*5,
                      JWT_SECRET_KEY='test-jwt-secret-'*5, CAFE_CHECKOUT_URL='https://test.invalid/play')
    schema = 'cafe_test_' + uuid.uuid4().hex
    if url.startswith('postgresql'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'connect_args': {'options':f'-csearch_path={schema}'}}
    db = SQLAlchemy(app)
    JWTManager(app)
    for name in ['app','app.models','app.services','app.controllers','app.extension']:
        module = types.ModuleType(name); module.__path__ = []
        monkeypatch.setitem(sys.modules,name,module)
    module = types.ModuleType('app.extension.extensions'); module.db=db
    monkeypatch.setitem(sys.modules,'app.extension.extensions',module)
    def load(name,path):
        spec=importlib.util.spec_from_file_location(name,ROOT/path)
        module=importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules,name,module);spec.loader.exec_module(module)
        return module
    def model_module(name,model):
        m=types.ModuleType('app.models.'+name);setattr(m,model.__name__,model)
        monkeypatch.setitem(sys.modules,m.__name__,m)
    class Vendor(db.Model):
        __tablename__='vendors'
        id=db.Column(db.Integer,primary_key=True)
        cafe_name=db.Column(db.String,default='Test Cafe')
    class User(db.Model):
        __tablename__='users'
        id=db.Column(db.Integer,primary_key=True)
    class Console(db.Model):
        __tablename__='consoles'
        id=db.Column(db.Integer,primary_key=True)
        vendor_id=db.Column(db.Integer)
        console_number=db.Column(db.Integer,default=1)
    class ConsoleLinkSession(db.Model):
        __tablename__='console_link_sessions'
        id=db.Column(db.Integer,primary_key=True)
        vendor_id=db.Column(db.Integer)
        console_id=db.Column(db.Integer)
        status=db.Column(db.String)
        session_token=db.Column(db.String)
    class VendorStaff(db.Model):
        __tablename__='vendor_staff'
        id=db.Column(db.Integer,primary_key=True)
        vendor_id=db.Column(db.Integer)
        name=db.Column(db.String)
        role=db.Column(db.String)
        is_active=db.Column(db.Boolean,default=True)
    class VendorRolePermission(db.Model):
        __tablename__='vendor_role_permissions'
        id=db.Column(db.Integer,primary_key=True)
        vendor_id=db.Column(db.Integer)
        role=db.Column(db.String)
        permission=db.Column(db.String)
    class ExtraServiceCategory(db.Model):
        __tablename__='extra_service_categories'
        id=db.Column(db.Integer,primary_key=True)
        vendor_id=db.Column(db.Integer)
        is_active=db.Column(db.Boolean,default=True)
    class ExtraServiceMenu(db.Model):
        __tablename__='extra_service_menus'
        id=db.Column(db.Integer,primary_key=True)
        category_id=db.Column(db.Integer,db.ForeignKey('extra_service_categories.id'))
        name=db.Column(db.String,default='Snack')
        price=db.Column(db.Float,default=50)
        stock_quantity=db.Column(db.Integer,default=10)
        is_active=db.Column(db.Boolean,default=True)
    for name,model in [('vendor',Vendor),('user',User),('console',Console),('console_link_session',ConsoleLinkSession),('vendorStaff',VendorStaff),('vendorRolePermission',VendorRolePermission),('extraServiceMenu',ExtraServiceMenu),('extraServiceCategory',ExtraServiceCategory)]:
        model_module(name,model)
    models=load('app.models.cafe_wallet','app/models/cafe_wallet.py')
    service=load('app.services.cafe_wallet_service','app/services/cafe_wallet_service.py')
    booking_service=load('app.services.cafe_booking_service','app/services/cafe_booking_service.py')
    rbac=load('app.services.rbac_service','app/services/rbac_service.py')
    controller=load('app.controllers.cafe_wallet_controller','app/controllers/cafe_wallet_controller.py')
    socket=types.ModuleType('app.services.websocket_service')
    from unittest.mock import Mock
    socket.socketio=Mock();monkeypatch.setitem(sys.modules,socket.__name__,socket)
    app.register_blueprint(controller.bp_cafe)
    with app.app_context():
        if url.startswith('postgresql'):
            with db.engine.begin() as conn:conn.execute(text(f'CREATE SCHEMA {schema}'))
        db.create_all()
        if url.startswith('postgresql'):
            raw=db.engine.raw_connection()
            try:
                raw.cursor().execute((ROOT/'sql/20260922_cafe_wallet.sql').read_text());raw.commit()
                raw.cursor().execute((ROOT/'sql/20260923_unified_kiosk_qr.sql').read_text());raw.commit()
            finally:raw.close()
            db.session.execute(text('CREATE TABLE vendor_1_console_availability (console_id integer, is_available boolean)'))
            db.session.execute(text('CREATE TABLE vendor_1_dashboard (console_id integer, book_status varchar, book_id integer, date date, start_time time, end_time time)'))
            db.session.execute(text('INSERT INTO vendor_1_console_availability VALUES (1,true),(2,true)'))
            db.session.execute(text('SELECT cafe_install_console_guards(1)'))
        db.session.execute(text('CREATE TABLE bookings (id integer PRIMARY KEY, user_id integer, game_id integer, status varchar, squad_details json, access_code_id integer)'))
        db.session.execute(text('CREATE TABLE available_games (id integer PRIMARY KEY, vendor_id integer, game_name varchar)'))
        db.session.execute(text('CREATE TABLE available_game_console (available_game_id integer, console_id integer)'))
        db.session.execute(text('CREATE TABLE transactions (id integer PRIMARY KEY, booking_id integer, vendor_id integer, user_id integer, booking_type varchar, amount numeric, settlement_status varchar)'))
        if not url.startswith('postgresql'):
            db.session.execute(text('CREATE TABLE vendor_1_dashboard (console_id integer, book_status varchar, book_id integer, date date, start_time time, end_time time)'))
        db.session.add_all([Vendor(id=1),Vendor(id=2),User(id=1),User(id=2),Console(id=1,vendor_id=1),Console(id=2,vendor_id=1),ConsoleLinkSession(id=1,vendor_id=1,console_id=1,status='active',session_token='agent-secret'),ConsoleLinkSession(id=2,vendor_id=1,console_id=2,status='active',session_token='agent-other'),VendorStaff(id=1,vendor_id=1,name='Sam',role='staff'),ExtraServiceCategory(id=1,vendor_id=1),ExtraServiceMenu(id=1,category_id=1)])
        db.session.add(models.CafePaymentPolicy(vendor_id=1,settings=dict(service.DEFAULT_POLICY,self_service=True)))
        db.session.commit()
    result=types.SimpleNamespace(app=app,db=db,m=models,s=service,c=controller,rbac=rbac,b=booking_service,Link=ConsoleLinkSession,pg=url.startswith('postgresql'))
    yield result
    with app.app_context():
        db.session.remove()
        if result.pg:
            with db.engine.begin() as conn:conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        else:db.drop_all()
        db.engine.dispose()


ACTOR={'id':'1','name':'Sam'}

def fund(e,user=1,amount=20000):
    if not e.m.CafeShift.query.first():
        e.db.session.add(e.m.CafeShift(id='shift',vendor_id=1,actor_id='1',actor_name='Sam',open_key='1:1',opening_cash=1000))
        e.db.session.flush()
    entry=e.s.topup(1,user,{'amount':amount,'method':'cash','idempotency_key':f'topup-user-{user}'},ACTOR)
    e.db.session.commit()
    return entry


def staff_token(e,role='staff',vid=1):
    with e.app.test_request_context():
        return e.rbac.create_access_token_payload(vid,'1','Sam',role)['token']


def auth(token):return {'Authorization':'Bearer '+token}


def gamer(e,user=1):
    now=datetime.utcnow()
    return jwt.encode({'sub':str(user),'aud':'cafe-checkout','scope':'cafe_gamer','iat':now,'exp':now+timedelta(minutes=10)},e.app.config['JWT_SECRET_KEY'],algorithm='HS256')


def test_reserve_ack_is_idempotent_and_money_is_conserved(env):
    e=env
    with e.app.app_context():
        fund(e)
        link=e.db.session.get(e.Link,1)
        s=e.s.reserve(1,1,link,60,'checkout-1');e.db.session.commit()
        assert e.s.reserve(1,1,link,60,'checkout-1').id==s.id
        w=e.db.session.get(e.m.CafeWallet,(1,1));assert (w.balance,w.reserved)==(20000,10000)
        e.s.acknowledge(s.id,link,s.command_token,True);e.db.session.commit()
        e.s.acknowledge(s.id,link,s.command_token,True);e.db.session.commit()
        assert (w.balance,w.reserved)==(10000,0)
        assert e.m.CafeLedger.query.filter_by(kind='capture').count()==1
        assert s.ends_at-s.started_at==timedelta(minutes=60)


def test_failed_and_late_ack_release_without_charge(env):
    e=env
    with e.app.app_context():
        fund(e);link=e.db.session.get(e.Link,1)
        s=e.s.reserve(1,1,link,60,'checkout-1');s.deadline=datetime.utcnow()-timedelta(seconds=1);e.db.session.commit()
        e.s.expire_sessions()
        e.s.acknowledge(s.id,link,s.command_token,True);e.db.session.commit()
        w=e.db.session.get(e.m.CafeWallet,(1,1))
        assert s.state=='failed' and s.console_claim is None
        assert (w.balance,w.reserved)==(20000,0)
        assert not e.m.CafeLedger.query.filter_by(kind='capture').first()
        if e.pg:assert e.db.session.execute(text('SELECT is_available FROM vendor_1_console_availability WHERE console_id=1')).scalar()


def test_other_pc_cannot_acknowledge(env):
    e=env
    with e.app.app_context():
        fund(e);s=e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'checkout-1');e.db.session.commit()
        with pytest.raises(e.s.CafeError):e.s.acknowledge(s.id,e.db.session.get(e.Link,2),s.command_token,True)
        with pytest.raises(e.s.CafeError):e.s.acknowledge(s.id,e.db.session.get(e.Link,1),'wrong',True)


def test_topup_dedup_refund_and_history_immutability(env):
    e=env
    with e.app.app_context():
        original=fund(e)
        repeated=e.s.topup(1,1,{'amount':20000,'method':'cash','idempotency_key':'topup-user-1'},ACTOR)
        assert repeated.id==original.id
        with pytest.raises(e.s.CafeError):e.s.topup(1,1,{'amount':30000,'method':'cash','idempotency_key':'topup-user-1'},ACTOR)
        e.s.refund(1,original.id,{'reason':'Duplicate desk collection','idempotency_key':'refund-001'},ACTOR);e.db.session.commit()
        assert e.db.session.get(e.m.CafeWallet,(1,1)).balance==0
        with pytest.raises(e.s.CafeError):e.s.refund(1,original.id,{'reason':'Again','idempotency_key':'refund-002'},ACTOR)
        original.amount=1
        with pytest.raises(ValueError):e.db.session.commit()
        e.db.session.rollback()
        if e.pg:
            with pytest.raises(Exception):
                e.db.session.execute(text('DELETE FROM cafe_wallet_ledger'))
            e.db.session.rollback()


def test_http_auth_policy_shift_and_food_separation(env):
    e=env;client=e.app.test_client();staff=staff_token(e);headers=auth(staff)
    assert client.post('/api/cafe/1/wallets/1/topups',json={'amount':100,'method':'cash','idempotency_key':'topup-001'}).status_code==401
    assert client.get('/api/cafe/2/policy',headers=headers).status_code==403
    assert client.put('/api/cafe/1/policy',headers=headers,json=e.s.DEFAULT_POLICY).status_code==403
    assert client.post('/api/cafe/1/wallets/1/topups',headers=headers,json={'amount':100,'method':'cash','idempotency_key':'topup-001'}).status_code==409
    opened=client.post('/api/cafe/1/shifts/open',headers=headers,json={'opening_cash':1000}).json
    assert client.post('/api/cafe/1/wallets/1/topups',headers=headers,json={'amount':20000,'method':'cash','idempotency_key':'topup-001'}).status_code==200
    assert client.post('/api/cafe/1/wallets/1/topups',headers=headers,json={'amount':5000,'method':'cafe_upi','idempotency_key':'topup-002'}).status_code==200
    closed=client.post(f"/api/cafe/1/shifts/{opened['id']}/close",headers=headers,json={'counted_cash':20000}).json
    assert closed['expected_cash']==21000 and closed['upi_receipts']==5000
    qr=client.post('/api/cafe/agent/qr',headers=auth('agent-secret')).json['token']
    gh=auth(gamer(e));body={'qr':qr,'minutes':60,'payment_method':'cafe_wallet','expected_amount':10000,'idempotency_key':'checkout-01'}
    assert client.get('/api/cafe/checkout?qr='+qr,headers=gh).status_code==200
    response=client.post('/api/cafe/checkout',headers=gh,json=body)
    assert response.status_code==202, response.json
    assert 'command_token' not in response.json
    assert client.post('/api/cafe/checkout',headers=gh,json=dict(body,payment_method='hash_wallet')).status_code==400
    order=client.post('/api/cafe/food/orders',headers=gh,json={'qr':qr,'items':[{'id':1,'quantity':2}],'idempotency_key':'food-order-1'})
    assert order.status_code==201,order.json
    assert order.json['collector']=='vendor'
    with e.app.app_context():
        assert e.db.session.get(e.m.CafeWallet,(1,1)).balance==25000
        assert e.m.CafeLedger.query.filter_by(kind='food_collection').count()==0
    assert client.post('/api/cafe/1/logout',headers=headers).status_code==200
    assert client.get('/api/cafe/1/policy',headers=headers).status_code==401


def test_insufficient_funds_and_same_pc_conflict(env):
    e=env
    with e.app.app_context():
        fund(e,1);fund(e,2)
        link=e.db.session.get(e.Link,1)
        s=e.s.reserve(1,1,link,60,'checkout-01');e.db.session.commit()
        with pytest.raises(e.s.CafeError):e.s.reserve(1,2,link,60,'checkout-02')
        e.db.session.rollback()
        w=e.db.session.get(e.m.CafeWallet,(1,2));w.balance=0;e.db.session.commit()
        with pytest.raises(e.s.CafeError):e.s.reserve(1,2,e.db.session.get(e.Link,2),60,'checkout-03')
        e.db.session.rollback()
        assert e.m.CafePlaySession.query.count()==1


def test_postgres_concurrent_checkout_and_legacy_guards(env):
    e=env
    if not e.pg:pytest.skip('Requires PostgreSQL row locks')
    with e.app.app_context():fund(e,1);fund(e,2)
    barrier=threading.Barrier(2)
    def checkout(user):
        with e.app.app_context():
            link=e.db.session.get(e.Link,1);barrier.wait()
            try:
                session=e.s.reserve(1,user,link,60,f'checkout-{user}');e.db.session.commit();return session.id
            except e.s.CafeError:
                e.db.session.rollback();return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(checkout,[1,2]))
    assert sum(r is not None for r in results)==1
    with e.app.app_context():
        assert e.m.CafePlaySession.query.count()==1
        e.db.session.execute(text('UPDATE vendor_1_console_availability SET is_available=true WHERE console_id=1'));e.db.session.commit()
        assert e.db.session.execute(text('SELECT is_available FROM vendor_1_console_availability WHERE console_id=1')).scalar() is False
        with pytest.raises(Exception):e.db.session.execute(text("INSERT INTO vendor_1_dashboard (console_id,book_status) VALUES (1,'current')"))
        e.db.session.rollback()
        assert sum(w.reserved for w in e.m.CafeWallet.query.all())==10000


def test_websocket_rooms_require_real_pc_credentials(env,monkeypatch):
    from flask_socketio import SocketIO
    e=env;io=SocketIO(e.app,async_mode='threading')
    e.c.register_cafe_runtime(e.app,io)
    monkeypatch.setattr(sys.modules['app.services.websocket_service'],'socketio',io)
    bad=io.test_client(e.app,namespace='/cafe-agent',auth={'token':'bad'})
    assert not bad.is_connected('/cafe-agent')
    first=io.test_client(e.app,namespace='/cafe-agent',auth={'token':'agent-secret'})
    second=io.test_client(e.app,namespace='/cafe-agent',auth={'token':'agent-other'})
    assert first.is_connected('/cafe-agent') and second.is_connected('/cafe-agent')
    with e.app.app_context():fund(e)
    client=e.app.test_client()
    qr=client.post('/api/cafe/agent/qr',headers=auth('agent-secret')).json['token']
    res=client.post('/api/cafe/checkout',headers=auth(gamer(e)),json={'qr':qr,'minutes':60,'payment_method':'cafe_wallet','expected_amount':10000,'idempotency_key':'ws-checkout-01'})
    assert res.status_code==202
    received=first.get_received('/cafe-agent')
    assert received[0]['name']=='session.prepare'
    assert second.get_received('/cafe-agent')==[]
    command=received[0]['args'][0]
    ack=client.post('/api/cafe/agent/ack',headers=auth('agent-secret'),json={'session_id':command['id'],'command_token':command['command_token'],'success':True})
    assert ack.json['state']=='active'
    first.disconnect(namespace='/cafe-agent');second.disconnect(namespace='/cafe-agent')


def test_policy_disabled_food_and_adjustment_permissions(env):
    e=env;client=e.app.test_client();staff=staff_token(e);owner=staff_token(e,'owner')
    with e.app.app_context():fund(e)
    assert client.post('/api/cafe/1/wallets/1/adjustments',headers=auth(staff),json={'amount':100,'reason':'Correction','idempotency_key':'adjust-01'}).status_code==403
    assert client.post('/api/cafe/1/wallets/1/adjustments',headers=auth(owner),json={'amount':100,'reason':'Correction','idempotency_key':'adjust-01'}).status_code==200
    settings=dict(e.s.DEFAULT_POLICY,food_ordering=False)
    assert client.put('/api/cafe/1/policy',headers=auth(owner),json=settings).status_code==200
    qr=client.post('/api/cafe/agent/qr',headers=auth('agent-secret')).json['token']
    assert client.post('/api/cafe/checkout',headers=auth(gamer(e)),json={'qr':qr,'minutes':60,'payment_method':'cafe_wallet','expected_amount':10000,'idempotency_key':'disabled-checkout'}).status_code==403
    assert client.get('/api/cafe/food/menu?qr='+qr,headers=auth(gamer(e))).status_code==403
    assert client.get('/api/cafe/checkout?qr=tampered',headers=auth(gamer(e))).status_code==410


def test_concurrent_duplicate_ack_does_not_double_capture(env):
    e=env
    if not e.pg:pytest.skip('Requires PostgreSQL')
    with e.app.app_context():
        fund(e);session=e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'ack-race-01');e.db.session.commit()
        sid,command_token=session.id,session.command_token
    barrier=threading.Barrier(2)
    def ack(_):
        with e.app.app_context():
            # Preload the same old state to expose ORM identity-map races.
            e.db.session.get(e.m.CafePlaySession,sid)
            link=e.db.session.get(e.Link,1);barrier.wait()
            e.s.acknowledge(sid,link,command_token,True);e.db.session.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(ack,[1,2]))
    with e.app.app_context():
        assert e.db.session.get(e.m.CafeWallet,(1,1)).balance==10000
        assert e.m.CafeLedger.query.filter_by(kind='capture').count()==1


def test_expiry_and_shift_are_independent(env):
    e=env;token=staff_token(e)
    with e.app.app_context():
        fund(e)
        row=e.m.CafeStaffSession.query.first();row.expires_at=datetime.utcnow()-timedelta(seconds=1)
        e.db.session.commit();e.s.expire_sessions();e.s.expire_sessions()
        assert e.m.CafeAudit.query.filter_by(action='session.expired').count()==1
        assert e.m.CafeShift.query.first().closed_at is None
    assert e.app.test_client().get('/api/cafe/1/policy',headers=auth(token)).status_code==401


def test_email_login_otp_replay_attempt_limit_and_real_token(env,monkeypatch):
    e=env
    if not e.pg:pytest.skip('Requires PostgreSQL')
    from unittest.mock import Mock
    extension=types.ModuleType('db.extensions');extension.db=e.db;extension.mail=Mock()
    parent=types.ModuleType('db');parent.__path__=[]
    monkeypatch.setitem(sys.modules,'db',parent);monkeypatch.setitem(sys.modules,'db.extensions',extension)
    security=types.ModuleType('services.security');security.auth_required_self=lambda **kw:lambda fn:fn
    parent=types.ModuleType('services');parent.__path__=[]
    monkeypatch.setitem(sys.modules,'services',parent);monkeypatch.setitem(sys.modules,'services.security',security)
    source=ROOT.parent/'hfg-booking/controllers/cafe_checkout_controller.py'
    spec=importlib.util.spec_from_file_location('booking_cafe_login',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    e.app.config['MAIL_DEFAULT_SENDER']='test@example.invalid'
    e.app.register_blueprint(module.cafe_checkout_blueprint,url_prefix='/api')
    with e.app.app_context():
        raw=e.db.engine.raw_connection()
        try:
            raw.cursor().execute((ROOT.parent/'hfg-booking/sql/20260922_cafe_login.sql').read_text());raw.commit()
        finally:raw.close()
        e.db.session.execute(text('CREATE TABLE contact_info (parent_id integer,parent_type varchar,email varchar)'))
        e.db.session.execute(text("INSERT INTO contact_info VALUES (1,'user','gamer@example.invalid')"));e.db.session.commit()
    client=e.app.test_client()
    challenge=client.post('/api/cafe-checkout/login/request',json={'email':'gamer@example.invalid'})
    assert challenge.status_code==200,challenge.json
    message=extension.mail.send.call_args[0][0]
    import re
    code=re.search(r'\b\d{6}\b',message.body).group()
    payload={'challenge_id':challenge.json['challenge_id'],'code':code}
    response=client.post('/api/cafe-checkout/login/verify',json=payload)
    assert response.status_code==200,response.json
    claims=jwt.decode(response.json['token'],e.app.config['JWT_SECRET_KEY'],algorithms=['HS256'],audience='cafe-checkout')
    assert claims['sub']=='1' and claims['scope']=='cafe_gamer'
    assert client.post('/api/cafe-checkout/login/verify',json=payload).status_code==401
    challenge=client.post('/api/cafe-checkout/login/request',json={'email':'gamer@example.invalid'}).json
    for _ in range(5):assert client.post('/api/cafe-checkout/login/verify',json={'challenge_id':challenge['challenge_id'],'code':'bad'}).status_code==401
    code=re.search(r'\b\d{6}\b',extension.mail.send.call_args[0][0].body).group()
    assert client.post('/api/cafe-checkout/login/verify',json={'challenge_id':challenge['challenge_id'],'code':code}).status_code==401
    for _ in range(3):client.post('/api/cafe-checkout/login/request',json={'email':'gamer@example.invalid'})
    assert client.post('/api/cafe-checkout/login/request',json={'email':'gamer@example.invalid'}).status_code==429


def test_legacy_payment_policy_cannot_collect_for_wallet_cafe(env,monkeypatch):
    e=env
    from flask import jsonify
    parent=types.ModuleType('db');parent.__path__=[]
    extension=types.ModuleType('db.extensions');extension.db=e.db
    monkeypatch.setitem(sys.modules,'db',parent);monkeypatch.setitem(sys.modules,'db.extensions',extension)
    spec=importlib.util.spec_from_file_location('cafe_policy_guard',ROOT.parent/'hfg-booking/services/cafe_payment_policy.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    e.app.before_request(module.enforce_cafe_payment_policy)
    e.app.add_url_rule('/legacy-order','create_order',lambda:jsonify(ok=True),methods=['POST'])
    client=e.app.test_client()
    assert client.post('/legacy-order',json={'vendor_id':1}).status_code==403
    assert client.post('/legacy-order',json={}).status_code==400
    assert client.post('/legacy-order',json={'vendor_id':2}).status_code==200


def test_price_change_does_not_reserve_or_debit(env):
    e=env
    with e.app.app_context():
        fund(e)
        with pytest.raises(e.s.CafeError):
            e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'price-change-1',expected_amount=5000)
        e.db.session.rollback()
        assert e.db.session.get(e.m.CafeWallet,(1,1)).reserved==0
        assert e.m.CafePlaySession.query.count()==0


def test_food_store_collection_is_not_allowed_at_cafe(env):
    e=env;client=e.app.test_client();staff=staff_token(e)
    qr=client.post('/api/cafe/agent/qr',headers=auth('agent-secret')).json['token']
    created=client.post('/api/cafe/food/orders',headers=auth(gamer(e)),json={'qr':qr,'items':[{'id':1,'quantity':1}],'idempotency_key':'store-food-01'})
    assert created.status_code==201
    assert client.post('/api/cafe/1/food/orders/'+created.json['id']+'/collect',headers=auth(staff),json={'method':'cash'}).status_code==403


def seed_booking(e, *, paid=True, contiguous=False):
    now=datetime.now(e.b.IST).replace(microsecond=0)
    start=now-timedelta(minutes=5);end=now+timedelta(minutes=25)
    e.db.session.execute(text("INSERT INTO available_games VALUES (1,1,'Gaming PC')"))
    e.db.session.execute(text('INSERT INTO available_game_console VALUES (1,1),(1,2)'))
    for bid,begin,finish in [(101,start,end)]+([(102,end,end+timedelta(minutes=30))] if contiguous else []):
        e.db.session.execute(text("INSERT INTO bookings VALUES (:id,1,1,'confirmed','{}',99)"),{'id':bid})
        e.db.session.execute(text("INSERT INTO vendor_1_dashboard (book_id,book_status,date,start_time,end_time) VALUES (:id,'upcoming',:day,:start,:end)"),{'id':bid,'day':begin.date(),'start':begin.time(),'end':finish.time()})
        e.db.session.execute(text("INSERT INTO transactions VALUES (:id,:id,1,1,'booking',100,:status)"),{'id':bid,'status':'completed' if paid else 'pending'})
    e.db.session.commit()


def test_single_qr_paid_booking_no_second_charge(env):
    e=env
    if not e.pg:pytest.skip('PostgreSQL booking integration')
    with e.app.app_context():
        fund(e);seed_booking(e,contiguous=True)
        before=e.m.CafeLedger.query.count();client=e.app.test_client()
        qr=client.post('/api/cafe/agent/qr',headers=auth('agent-secret')).json['token']
        gh=auth(gamer(e));quote=client.get('/api/cafe/checkout',query_string={'qr':qr},headers=gh).json
        assert len(quote['bookings'])==1 and quote['bookings'][0]['booking_ids']==[101,102]
        assert quote['bookings'][0]['can_start']
        body={'qr':qr,'booking_id':101,'payment_method':'existing_booking','idempotency_key':'booking-checkout-1'}
        response=client.post('/api/cafe/checkout',json=body,headers=gh)
        assert response.status_code==202,response.json
        sid=response.json['id'];assert response.json['amount']==0
        assert client.post('/api/cafe/checkout',json=body,headers=gh).json['id']==sid
        session=e.db.session.get(e.m.CafePlaySession,sid);link=e.db.session.get(e.Link,1)
        end=session.booking_end
        e.s.acknowledge(sid,link,session.command_token,True);e.db.session.commit()
        e.s.acknowledge(sid,link,session.command_token,True);e.db.session.commit()
        assert session.state=='active' and session.ends_at==end
        assert e.m.CafeLedger.query.count()==before
        assert e.db.session.get(e.m.CafeWallet,(1,1)).balance==20000
        assert e.db.session.execute(text("SELECT count(*) FROM bookings WHERE status='checked_in'")).scalar()==2
        assert e.db.session.execute(text("SELECT count(*) FROM vendor_1_dashboard WHERE book_status='current' AND console_id=1")).scalar()==2
        assert client.get('/api/cafe/checkout',query_string={'qr':qr},headers=gh).json['active_session_id']==sid
        with pytest.raises(Exception):e.db.session.execute(text("UPDATE vendor_1_dashboard SET console_id=2 WHERE book_id=101"))
        e.db.session.rollback()
        session.ends_at=datetime.utcnow()-timedelta(seconds=1);e.db.session.commit();e.s.expire_sessions()
        assert session.state=='completed' and session.console_claim is None
        assert e.db.session.execute(text("SELECT count(*) FROM bookings WHERE status='completed'")).scalar()==2


@pytest.mark.parametrize('change', ['unpaid','other_gamer','cancelled','future','wrong_pc','incompatible','squad'])
def test_existing_booking_eligibility_is_enforced(env,change):
    e=env
    if not e.pg:pytest.skip('PostgreSQL booking integration')
    with e.app.app_context():
        seed_booking(e,paid=change!='unpaid')
        sql={'cancelled':"UPDATE bookings SET status='cancelled'",'future':"UPDATE vendor_1_dashboard SET date=date+1",'wrong_pc':"UPDATE vendor_1_dashboard SET console_id=2",'incompatible':'DELETE FROM available_game_console WHERE console_id=1','squad':'''UPDATE bookings SET squad_details='{"player_count": 2}' '''}.get(change)
        if sql:e.db.session.execute(text(sql));e.db.session.commit()
        with pytest.raises(e.s.CafeError):e.b.reserve_booking(e.db.session.get(e.Link,1),2 if change=='other_gamer' else 1,101,'booking-rejected-1')
        e.db.session.rollback()
        assert e.m.CafeBookingClaim.query.count()==0
        assert e.m.CafeLedger.query.count()==0


@pytest.mark.parametrize('failure',['negative_ack','timeout','refund','cancel'])
def test_existing_booking_failed_start_releases_without_payment(env,failure):
    e=env
    if not e.pg:pytest.skip('PostgreSQL booking integration')
    with e.app.app_context():
        seed_booking(e);link=e.db.session.get(e.Link,1)
        s=e.b.reserve_booking(link,1,101,'booking-first-1');e.db.session.commit()
        with pytest.raises(Exception):e.db.session.execute(text("UPDATE vendor_1_dashboard SET book_status='current',console_id=1 WHERE book_id=101"))
        e.db.session.rollback()
        if failure=='timeout':s.deadline=datetime.utcnow()-timedelta(seconds=1)
        if failure=='refund':e.db.session.execute(text("UPDATE transactions SET settlement_status='refunded'"))
        if failure=='cancel':e.db.session.execute(text("UPDATE bookings SET status='cancelled'"))
        e.db.session.commit()
        e.s.acknowledge(s.id,link,s.command_token,failure!='negative_ack');e.db.session.commit()
        assert s.state=='failed' and s.console_claim is None
        assert e.m.CafeBookingClaim.query.count()==0 and e.m.CafeLedger.query.count()==0
        assert e.db.session.execute(text('SELECT is_available FROM vendor_1_console_availability WHERE console_id=1')).scalar()
        if failure in ('negative_ack','timeout'):
            retry=e.b.reserve_booking(link,1,101,'booking-retry-2');e.db.session.commit()
            assert retry.id!=s.id


def test_same_booking_cannot_start_on_two_pcs(env):
    e=env
    if not e.pg:pytest.skip('PostgreSQL row locks')
    with e.app.app_context():seed_booking(e)
    barrier=threading.Barrier(2)
    def attempt(link_id):
        with e.app.app_context():
            link=e.db.session.get(e.Link,link_id);barrier.wait()
            try:
                s=e.b.reserve_booking(link,1,101,f'concurrent-booking-{link_id}');e.db.session.commit();return s.id
            except e.s.CafeError:
                e.db.session.rollback();return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,[1,2]))
    assert sum(r is not None for r in results)==1
    with e.app.app_context():assert e.m.CafeBookingClaim.query.count()==1


@pytest.mark.parametrize('change',["UPDATE bookings SET status='cancelled'", "UPDATE transactions SET settlement_status='refunded'"])
def test_active_booking_cancellation_or_refund_stops_session(env,change):
    e=env
    if not e.pg:pytest.skip('PostgreSQL booking integration')
    with e.app.app_context():
        seed_booking(e);link=e.db.session.get(e.Link,1)
        s=e.b.reserve_booking(link,1,101,'booking-active-1');e.db.session.commit()
        e.s.acknowledge(s.id,link,s.command_token,True);e.db.session.commit()
        e.db.session.execute(text(change));e.db.session.commit();e.s.expire_sessions()
        assert s.state=='cancelled' and s.console_claim is None
        assert e.m.CafeLedger.query.count()==0
