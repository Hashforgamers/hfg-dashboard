"""Run with KIOSK_TEST_DATABASE_URL pointing to a disposable PostgreSQL DB.

Loads production functions without application boot/upstream connections. Each test
uses a fresh schema; no production credentials or data are used.
"""
import ast
from datetime import datetime, timedelta, timezone, date, time
from zoneinfo import ZoneInfo
import os
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch
import uuid

from flask import Flask, jsonify, request, g
from flask_sqlalchemy import SQLAlchemy
import jwt
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
URL = os.getenv('KIOSK_TEST_DATABASE_URL')
db = SQLAlchemy()


def load(relative, **scope):
    tree = ast.parse((ROOT / relative).read_text())
    tree.body = [n for n in tree.body if not (isinstance(n, ast.ImportFrom) and (n.module or '').startswith('app.'))]
    exec(compile(tree, str(ROOT / relative), 'exec'), scope)
    return scope


security = load('app/services/kiosk_security.py', db=db)
runtime = load('app/services/kiosk_runtime.py', db=db, **{name: security[name] for name in
    ('KioskError', 'check_scope', 'positive_id', 'rate_limit', 'runtime_identity', 'vendor_lock')})


@unittest.skipUnless(URL, 'Set KIOSK_TEST_DATABASE_URL to a disposable PostgreSQL database')
class KioskTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY='test', JWT_SECRET_KEY='test-secret-' * 4,
                               SQLALCHEMY_DATABASE_URI=URL)
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.schema = 'kiosk_test_' + uuid.uuid4().hex
        with db.engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA {self.schema}'))
        # Dedicated engine connection keeps every transaction in this schema,
        # including independently committed rate-limit attempts.
        from sqlalchemy import event
        self.listener = lambda conn, branch: conn.exec_driver_sql(f'SET search_path TO {self.schema}')
        # Set at DBAPI checkout so SQLAlchemy does not open an implicit transaction.
        def set_schema(connection, record, proxy):
            with connection.cursor() as cursor:
                cursor.execute(f'SET search_path TO {self.schema}')
            connection.commit()
        self.checkout = set_schema
        event.listen(db.engine, 'checkout', self.checkout)
        with db.engine.begin() as conn:
            conn.execute(text('''
                CREATE TABLE consoles(id integer PRIMARY KEY, vendor_id integer);
                CREATE TABLE available_games(id integer PRIMARY KEY, vendor_id integer, game_name text);
                CREATE TABLE vendors(id integer PRIMARY KEY, cafe_name text);
                CREATE TABLE users(id integer PRIMARY KEY, name text);
                CREATE TABLE access_booking_codes(id integer PRIMARY KEY, access_code text UNIQUE);
                CREATE TABLE bookings(id integer PRIMARY KEY, game_id integer, access_code_id integer, status text, squad_details jsonb DEFAULT '{}');
                CREATE TABLE console_link_sessions(id integer PRIMARY KEY, console_id integer, vendor_id integer, kiosk_id text, session_token text, status text, ended_at timestamptz, close_reason text);
                CREATE TABLE vendor_1_dashboard(book_id integer PRIMARY KEY, user_id integer, username text, game_id integer, console_id integer, date date, start_time time, end_time time, book_status text);
                CREATE TABLE vendor_1_console_availability(console_id integer PRIMARY KEY, game_id integer, is_available boolean);
                INSERT INTO consoles VALUES(10,1),(11,1),(20,2);
                INSERT INTO available_games VALUES(100,1,'PC'),(200,2,'PC');
                INSERT INTO vendors VALUES(1,'Cafe'),(2,'Other');
                INSERT INTO users VALUES(77,'Player');
                INSERT INTO access_booking_codes VALUES(1,'123456');
                INSERT INTO bookings VALUES(5,100,1,'checked_in','{}');
                ALTER TABLE bookings ADD COLUMN user_id integer DEFAULT 77;
                INSERT INTO console_link_sessions VALUES(1,10,1,'machine-a','link-a','active',NULL,NULL),(2,11,1,'machine-b','link-b','active',NULL,NULL),(3,20,2,'machine-c','link-c','active',NULL,NULL);
                INSERT INTO vendor_1_console_availability VALUES(10,100,FALSE),(11,100,TRUE);
            '''))
            # Migration is idempotent and actually executed against PostgreSQL.
            migration = (ROOT / 'sql/20260922_kiosk_runtime.sql').read_text().replace('BEGIN;', '').replace('COMMIT;', '')
            conn.execute(text(migration))
            conn.execute(text(migration))
            commands=(ROOT/'sql/20261013_pc_command_ack.sql').read_text().replace('BEGIN;','').replace('COMMIT;','')
            conn.execute(text(commands));conn.execute(text(commands))
        now = datetime.now(runtime['IST']).replace(tzinfo=None)
        self.start = now - timedelta(minutes=1)
        self.end = now + timedelta(minutes=20)
        db.session.execute(text('INSERT INTO vendor_1_dashboard VALUES(5,77,\'Player\',100,10,:day,:start,:end,\'current\')'),
                           dict(day=self.start.date(), start=self.start.time(), end=self.end.time()))
        db.session.commit()
        self.calls = 0
        fake_routes = ModuleType('app.routes')
        fake_routes._invalidate_vendor_caches = Mock()
        fake_routes._share_chain_access_code = Mock()
        fake_ws = ModuleType('app.services.websocket_service')
        fake_ws._emit_to_kiosk = Mock()
        fake_ws.socketio = Mock()
        fake_security = ModuleType('app.services.kiosk_security')
        fake_security.__dict__.update(security)
        fake_runtime = ModuleType('app.services.kiosk_runtime')
        fake_runtime.__dict__.update(runtime)
        fake_commands=ModuleType('app.services.pc_commands')
        fake_commands.__dict__.update(load('app/services/pc_commands.py',db=db,KioskError=security['KioskError']))
        fake_extensions=ModuleType('app.services.session_extensions')
        fake_extensions.ready=lambda:False
        fake_extensions.attach=Mock()
        self.modules = patch.dict(sys.modules, {'app.routes': fake_routes,
            'app.services.websocket_service': fake_ws, 'app.services.kiosk_runtime': fake_runtime,
            'app.services.kiosk_security': fake_security,'app.services.pc_commands':fake_commands,
            'app.services.session_extensions':fake_extensions})
        self.modules.start()
        self.ws = fake_ws
        self.extensions = fake_extensions
        @self.app.errorhandler(security['KioskError'])
        def error(exc):
            db.session.rollback()
            return jsonify(status='error', code=exc.error_code), exc.code
        @self.app.route('/release/<gameid>/<console_id>/<vendor_id>', methods=['POST'])
        @security['transactional_device']
        def release(gameid, console_id, vendor_id):
            self.calls += 1
            db.session.execute(text("UPDATE vendor_1_dashboard SET book_status='completed' WHERE book_id=5"))
            return jsonify(ok=True), 200
        @self.app.route('/start', methods=['POST'])
        @runtime['secure_start']
        def start():
            self.calls += 1
            if request.get_json().get('fail'):
                db.session.execute(text("UPDATE vendor_1_dashboard SET book_status='completed' WHERE book_id=5"))
                return jsonify(error='simulated'), 500
            db.session.execute(text("UPDATE vendor_1_dashboard SET book_status='current',console_id=:cid WHERE book_id=5"),{'cid':request.get_json()['console_id']})
            return jsonify(booking_ids=[5]), 200
        # Execute actual unlink route body with no application bootstrap.
        tree = ast.parse((ROOT/'app/routes.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'kiosk_unlink')
        fn.decorator_list = []
        scope = dict(request=request, db=db, text=text, jsonify=jsonify,
                     _invalidate_vendor_caches=Mock())
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<unlink>', 'exec'), scope)
        self.app.add_url_rule('/unlink', view_func=scope['kiosk_unlink'], methods=['POST'])
        @self.app.route('/assign', methods=['POST'])
        @security['vendor_assignment']
        def assign():
            db.session.execute(text("UPDATE vendor_1_dashboard SET book_status='current' WHERE book_id=5"))
            if request.get_json().get('fail'):
                return jsonify(error='failed'), 409
            return jsonify(assigned_console_ids=[10]), 200
        self.client = self.app.test_client()

    def tearDown(self):
        from sqlalchemy import event
        self.modules.stop()
        db.session.remove()
        event.remove(db.engine, 'checkout', self.checkout)
        with db.engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA {self.schema} CASCADE'))
        db.engine.dispose()
        self.ctx.pop()

    def post(self, path, body=None, token='link-a', key=None):
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        if key:
            headers['Idempotency-Key'] = key
        return self.client.post(path, json=body or {}, headers=headers)

    def test_booking_qr_and_access_code_share_device_verification(self):
        self.app.add_url_rule('/verify',view_func=runtime['secure_start'](lambda:None,verify_only=True),methods=['POST'])
        db.session.execute(text("UPDATE access_booking_codes SET access_code='MKY628' WHERE id=1"));db.session.commit()
        for payload in [{'access_code':'mky628'},{'qr':{'booking_id':5,'access_code':'MKY628'}}]:
            result=self.post('/verify',payload)
            self.assertEqual(result.status_code,200)
            self.assertTrue(result.json['verified'])
            self.assertEqual(result.json['data']['booking_id'],5)
        self.assertEqual(db.session.execute(text('SELECT count(*) FROM kiosk_code_redemptions')).scalar(),0)
        self.assertEqual(self.calls,0)

    def test_rejection_logs_reference_and_assignment_without_secrets(self):
        controller=load('app/controllers/kiosk_controller.py',__name__=__name__,db=db,
            **{name:security[name] for name in ('KioskError','runtime_identity','positive_id','check_scope','rate_limit')},
            booking_window=runtime['booking_window'],expire_vendor=runtime['expire_vendor'],secure_start=runtime['secure_start'])
        controller['install_kiosk_errors'](self.app)
        @self.app.before_request
        def reference():g.request_id='test-reference'
        with self.assertLogs(self.app.logger,level='WARNING') as logs:
            result=self.post('/start',{'console_id':11,'access_code':'123456'},token='link-b')
        self.assertEqual(result.status_code,403)
        self.assertEqual(result.json['code'],'booking_console_mismatch')
        self.assertEqual(result.json['request_id'],'test-reference')
        output=' '.join(logs.output)
        self.assertIn('assigned_console_ids',output)
        self.assertIn('test-reference',output)
        self.assertNotIn('123456',output)
        self.assertNotIn('link-b',output)

    def test_unaccepted_pay_at_cafe_cannot_verify_or_unlock(self):
        self.app.add_url_rule('/verify',view_func=runtime['secure_start'](lambda:None,verify_only=True),methods=['POST'])
        db.session.execute(text("UPDATE bookings SET status='pending_acceptance' WHERE id=5"));db.session.commit()
        self.assertEqual(self.post('/verify',{'access_code':'123456'}).status_code,409)
        self.assertEqual(self.post('/start',{'console_id':10,'access_code':'123456'}).status_code,409)
        self.assertEqual(self.calls,0)

    def test_assigned_squad_pc_can_verify_but_unassigned_pc_cannot(self):
        self.app.add_url_rule('/verify',view_func=runtime['secure_start'](lambda:None,verify_only=True),methods=['POST'])
        db.session.execute(text("UPDATE bookings SET squad_details='{\"assigned_console_ids\":[10,11]}'::jsonb WHERE id=5"));db.session.commit()
        result=self.post('/verify',{'access_code':'123456'},token='link-b')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json['data']['console_id'],11)
        db.session.execute(text("UPDATE bookings SET squad_details='{}'::jsonb WHERE id=5"));db.session.commit()
        self.assertEqual(self.post('/verify',{'access_code':'123456'},token='link-b').status_code,403)
        self.assertEqual(db.session.execute(text('SELECT count(*) FROM kiosk_code_redemptions')).scalar(),0)

    def test_accepted_pay_at_cafe_verifies_and_starts_without_wallet(self):
        self.app.add_url_rule('/verify',view_func=runtime['secure_start'](lambda:None,verify_only=True),methods=['POST'])
        db.session.execute(text("UPDATE bookings SET status='confirmed' WHERE id=5"))
        db.session.execute(text("UPDATE vendor_1_dashboard SET book_status='upcoming',console_id=NULL WHERE book_id=5"));db.session.commit()
        result=self.post('/verify',{'qr':{'booking_id':5,'access_code':'123456'}})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json['data']['status'],'ready')
        self.assertEqual(db.session.execute(text('SELECT count(*) FROM kiosk_code_redemptions')).scalar(),0)
        started=self.post('/start',{'console_id':10,'access_code':'123456'})
        self.assertEqual(started.status_code,200)
        self.assertEqual(self.calls,1)

    def test_placeholder_pc_assignment_can_verify_and_start(self):
        self.app.add_url_rule('/verify',view_func=runtime['secure_start'](lambda:None,verify_only=True),methods=['POST'])
        db.session.execute(text("UPDATE bookings SET status='confirmed',squad_details='{\"assigned_console_ids\":[-1]}'::jsonb WHERE id=5"))
        db.session.execute(text("UPDATE vendor_1_dashboard SET book_status='upcoming',console_id=-1 WHERE book_id=5"));db.session.commit()
        self.assertEqual(self.post('/verify',{'access_code':'123456'}).status_code,200)
        self.assertEqual(db.session.execute(text('SELECT console_id FROM vendor_1_dashboard WHERE book_id=5')).scalar(),-1)
        self.assertEqual(db.session.execute(text('SELECT count(*) FROM kiosk_code_redemptions')).scalar(),0)
        self.assertEqual(self.post('/start',{'console_id':10,'access_code':'123456'}).status_code,200)
        self.assertEqual(db.session.execute(text('SELECT console_id FROM vendor_1_dashboard WHERE book_id=5')).scalar(),10)

    def test_alphanumeric_access_code_unlocks_assigned_pc(self):
        db.session.execute(text("UPDATE access_booking_codes SET access_code='MKY628' WHERE id=1"));db.session.commit()
        response=self.post('/start',{'console_id':10,'access_code':' mky628 '})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.calls,1)

    def test_real_assignment_starts_booking_in_same_transaction_as_redemption(self):
        from sqlalchemy.ext.automap import automap_base
        from flask import current_app
        db.session.execute(text("ALTER TABLE consoles ADD COLUMN console_number integer DEFAULT 1, ADD COLUMN model_number text DEFAULT 'PC'"))
        db.session.execute(text("UPDATE vendor_1_dashboard SET book_status='upcoming', console_id=-1 WHERE book_id=5"))
        db.session.execute(text("UPDATE bookings SET status='confirmed' WHERE id=5"))
        db.session.execute(text("UPDATE vendor_1_console_availability SET is_available=TRUE WHERE console_id=10"))
        db.session.commit()
        base = automap_base()
        base.prepare(autoload_with=db.engine)
        models = {}
        for name, table in [('Booking','bookings'),('AvailableGame','available_games'),('Console','consoles'),('User','users'),('Vendor','vendors')]:
            model = getattr(base.classes,table)
            model.query = db.session.query(model)
            models[name] = model
        tree = ast.parse((ROOT/'app/routes.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in
                     ('_booking_start_eligibility','_assign_console_to_multiple_bookings_core','kiosk_start_session','_share_chain_access_code')]
        for fn in tree.body: fn.decorator_list=[]
        scope = dict(db=db,text=text,request=request,jsonify=jsonify,current_app=current_app,g=g,
                     datetime=datetime,date=date,timedelta=timedelta,IST=ZoneInfo('Asia/Kolkata'),dt_timezone=timezone,
                     _resolve_console_group_from_name=lambda *a,**k:'pc',_invalidate_vendor_caches=Mock(),
                     KIOSK_GRACE_MIN=0,_emit_to_kiosk=Mock(),_ACCESS_CODE_ALPHABET='ABCDEFGHJKLMNPQRSTUVWXYZ23456789',**models)
        exec(compile(tree,'<production kiosk start>','exec'),scope)
        with self.app.test_request_context('/start',method='POST',json={'console_id':10,'access_code':'123456'},
                                          headers={'Authorization':'Bearer link-a'}):
            # Notification formatting is unrelated to the transaction; missing optional
            # fixture columns are intentionally logged by the production emitter.
            with patch.object(self.app.logger,'exception'):
                result = self.app.make_response(runtime['secure_start'](scope['kiosk_start_session'])())
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(result.json['data']['status'],'active')
        expected_start,_=runtime['utc_window'](self.start.date(),self.start.time(),self.end.time())
        self.assertEqual(result.json['data']['start_time'],expected_start.isoformat())
        self.assertEqual(result.json['data']['end_time'].split('+')[-1],'00:00')
        self.assertEqual(db.session.execute(text('SELECT console_id FROM kiosk_code_redemptions')).scalar_one(),10)
        self.assertEqual(db.session.execute(text('SELECT book_status FROM vendor_1_dashboard')).scalar_one(),'current')
        self.assertFalse(db.session.execute(text('SELECT is_available FROM vendor_1_console_availability WHERE console_id=10')).scalar_one())

    def test_phone_owned_start_and_wrong_owner(self):
        def start_phone():
            return jsonify(ok=True)
        handler=runtime['secure_start'](start_phone,phone=True)
        with self.app.test_request_context(json={'booking_id':5,'console_id':10}):
            g.cafe_user_id=77
            response=self.app.make_response(handler())
            self.assertEqual(response.status_code,200)
            self.ws._emit_to_kiosk.assert_called()
        with self.app.test_request_context(json={'booking_id':5,'console_id':10}):
            g.cafe_user_id=78
            with self.assertRaises(security['KioskError']) as caught:handler()
            self.assertEqual(caught.exception.error_code,'booking_not_owned')
        db.session.rollback()

    def scanned_pc_qr(self):
        """Real resolve_qr/signer from the cafe controller, with links read from this schema."""
        from types import SimpleNamespace
        from urllib.parse import urlencode
        from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
        service = ast.parse((ROOT/'app/services/cafe_wallet_service.py').read_text())
        service.body = [n for n in service.body if isinstance(n, ast.ClassDef) and n.name == 'CafeError']
        errors = {}
        exec(compile(service, '<cafe errors>', 'exec'), errors)
        tree = ast.parse((ROOT/'app/controllers/cafe_wallet_controller.py').read_text())
        tree.body = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in ('signer', 'resolve_qr'))
                     or (isinstance(n, ast.Assign) and any(getattr(t, 'id', None) == 'QR_VALIDITY_SECONDS' for t in n.targets))]
        def get(_model, link_id):
            row = db.session.execute(text('SELECT id, console_id, vendor_id, status FROM console_link_sessions WHERE id=:id'),
                                     {'id': link_id}).mappings().first()
            return SimpleNamespace(**row) if row else None
        scope = dict(current_app=self.app, URLSafeTimedSerializer=URLSafeTimedSerializer, BadSignature=BadSignature,
                     SignatureExpired=SignatureExpired, CafeError=errors['CafeError'], ConsoleLinkSession=object,
                     db=SimpleNamespace(session=SimpleNamespace(get=get)))
        exec(compile(tree, '<cafe qr>', 'exec'), scope)
        controller = ModuleType('app.controllers.cafe_wallet_controller')
        controller.resolve_qr = scope['resolve_qr']
        service_module = ModuleType('app.services.cafe_wallet_service')
        service_module.CafeError = errors['CafeError']
        self.qr_modules = patch.dict(sys.modules, {'app.controllers.cafe_wallet_controller': controller,
                                                   'app.services.cafe_wallet_service': service_module})
        self.qr_modules.start()
        self.addCleanup(self.qr_modules.stop)
        def checkout_url(link_id):
            return 'https://hashforgamers.com/cafe/checkout?' + urlencode({'qr': scope['signer']().dumps({'link_id': link_id})})
        return checkout_url

    def phone_start(self, console_id, user_id=77):
        handler = runtime['secure_start'](lambda: jsonify(ok=True), phone=True)
        with self.app.test_request_context(json={'booking_id': 5, 'console_id': console_id, 'vendor_id': 1, 'game_id': 100}):
            g.cafe_user_id = user_id
            try:
                return self.app.make_response(handler())
            finally:
                db.session.rollback()

    def test_phone_start_accepts_scanned_pc_checkout_qr(self):
        # The ticket scanner forwards the PC's checkout URL as console_id when it is not a number.
        checkout_url = self.scanned_pc_qr()
        response = self.phone_start(checkout_url(1))
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.ws._emit_to_kiosk.call_args[0][0], 10)
        self.ws._emit_to_kiosk.reset_mock()
        bare_token = checkout_url(1).split('qr=', 1)[1]
        from urllib.parse import unquote
        self.assertEqual(self.phone_start(unquote(bare_token)).status_code, 200)
        self.assertEqual(self.ws._emit_to_kiosk.call_args[0][0], 10)

    def test_phone_start_keeps_numeric_and_json_console_ids(self):
        self.scanned_pc_qr()
        for value in (10, '10', ' 10 ', '{"type":"scan_and_play","console_id":10,"kiosk_id":"machine-a"}'):
            self.ws._emit_to_kiosk.reset_mock()
            response = self.phone_start(value)
            self.assertEqual(response.status_code, 200, (value, response.json))
            self.assertEqual(self.ws._emit_to_kiosk.call_args[0][0], 10)

    def test_phone_start_scanned_qr_rejections(self):
        checkout_url = self.scanned_pc_qr()
        cases = [
            (checkout_url(2), 'booking_console_mismatch'),   # same cafe, PC not assigned to the ticket
            (checkout_url(3), 'booking_scope_mismatch'),     # PC belongs to another cafe
            ('https://hashforgamers.com/cafe/checkout?qr=forged', 'pc_qr_expired'),
            ('https://hashforgamers.com/somewhere-else', 'invalid_pc_qr'),
            ('{"kiosk_id":"machine-a"}', 'invalid_id'),
            ('{not json', 'invalid_pc_qr'),
            ('', 'invalid_id'),
        ]
        for value, code in cases:
            with self.assertRaises(security['KioskError'], msg=value) as caught:
                self.phone_start(value)
            self.assertEqual(caught.exception.error_code, code, value)
        db.session.execute(text("UPDATE console_link_sessions SET status='ended' WHERE id=1"));db.session.commit()
        with self.assertRaises(security['KioskError']) as caught:
            self.phone_start(checkout_url(1))
        self.assertEqual(caught.exception.error_code, 'pc_qr_expired')
        with self.assertRaises(security['KioskError']) as caught:
            self.phone_start(checkout_url(1), user_id=78)
        self.assertEqual(caught.exception.error_code, 'booking_not_owned')

    def test_command_identity_acknowledgement_scope_and_replay(self):
        from app.services.pc_commands import issue,acknowledge
        first=issue(1,10,5);db.session.commit()
        self.assertEqual(issue(1,10,5)['command_id'],first['command_id'])
        other={'kind':'kiosk','vendor_id':1,'console_id':11}
        with self.assertRaises(security['KioskError']):acknowledge(other,{'command_id':first['command_id'],'success':True})
        db.session.rollback()
        identity={'kind':'kiosk','vendor_id':1,'console_id':10}
        result=acknowledge(identity,{'command_id':first['command_id'],'success':True});db.session.commit()
        self.assertTrue(result['acknowledged'])
        self.assertTrue(acknowledge(identity,{'command_id':first['command_id'],'success':True})['acknowledged'])
        db.session.rollback()
        with self.assertRaises(security['KioskError']):acknowledge(identity,{'command_id':first['command_id'],'success':False})
        db.session.rollback()

    def test_phone_rejects_assignment_and_unaccepted_booking(self):
        handler=runtime['secure_start'](lambda:jsonify(ok=True),phone=True)
        with self.app.test_request_context(json={'booking_id':5,'console_id':11}):
            g.cafe_user_id=77
            with self.assertRaises(security['KioskError']) as caught:handler()
            self.assertEqual(caught.exception.error_code,'booking_console_mismatch')
        db.session.rollback()
        db.session.execute(text("UPDATE bookings SET status='pending_acceptance' WHERE id=5"));db.session.commit()
        with self.app.test_request_context(json={'booking_id':5,'console_id':10}):
            g.cafe_user_id=77
            with self.assertRaises(security['KioskError']) as caught:handler()
            self.assertEqual(caught.exception.error_code,'booking_not_accepted')
        db.session.rollback()

    def test_released_squad_console_cannot_continue(self):
        db.session.execute(text("UPDATE bookings SET squad_details=CAST(:details AS jsonb) WHERE id=5"),
                           {'details':'{"assigned_console_ids":[11],"released_console_ids":[10]}'})
        db.session.commit()
        self.assertEqual(runtime['booking_window'](1,5,10)['status'],'expired')
        self.assertEqual(runtime['booking_window'](1,5,11)['status'],'active')

    def test_used_code_cannot_start_later_booking(self):
        self.assertEqual(self.post('/start',{'console_id':10,'access_code':'123456'}).status_code,200)
        db.session.execute(text("UPDATE vendor_1_dashboard SET book_status='completed' WHERE book_id=5"))
        db.session.execute(text("INSERT INTO bookings VALUES(6,100,1,'confirmed','{}')"))
        db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES(6,77,'Player',100,NULL,:day,:start,:end,'upcoming')"),
                           {'day':self.start.date(),'start':self.start.time(),'end':self.end.time()})
        db.session.commit()
        result=self.post('/start',{'console_id':10,'access_code':'123456'})
        self.assertEqual(result.status_code,409,result.json)

    def socket_server(self):
        from flask import session
        from flask_socketio import SocketIO, join_room, leave_room, emit, disconnect
        import threading
        from typing import Dict, Any
        from types import SimpleNamespace
        socket = SocketIO(self.app, async_mode='threading')
        tree = ast.parse((ROOT/'app/services/websocket_service.py').read_text())
        names = ('register_dashboard_events','_socket_identity','_socket_console_scope','_emit_to_kiosk')
        tree.body = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        scope = dict(socketio=socket, session=session, g=g, db=db, text=text,
                     join_room=join_room, leave_room=leave_room, emit=emit, disconnect=disconnect,
                     linked_identity=security['linked_identity'], vendor_identity=security['vendor_identity'],
                     KioskError=security['KioskError'], Dict=Dict, Any=Any, _log_info=Mock(), _log_err=Mock(),
                     _log_warn=Mock(), _lock=threading.Lock(), _joined_vendor_ids=set(),
                     _upstream_sio=SimpleNamespace(connected=False))
        exec(compile(tree,'<socket handlers>','exec'),scope)
        scope['register_dashboard_events']()
        return socket,scope

    def test_socket_auth_room_binding_and_revocation(self):
        socket,scope = self.socket_server()
        self.assertFalse(socket.test_client(self.app).is_connected())
        self.assertFalse(socket.test_client(self.app,auth={'session_token':'link-a','console_id':11}).is_connected())
        client = socket.test_client(self.app,auth={'session_token':'link-a','console_id':10})
        other = socket.test_client(self.app,auth={'session_token':'link-b','console_id':11})
        self.assertTrue(client.is_connected())
        scope['_emit_to_kiosk'](10,'unlock_request',{'console_id':10})
        self.assertEqual(len(client.get_received()),1)
        self.assertEqual(other.get_received(),[])
        self.post('/unlink',{'session_token':'link-a'})
        scope['_emit_to_kiosk'](10,'unlock_request',{'console_id':10})
        self.assertEqual(client.get_received(),[])
        other.emit('kiosk_join',{'kiosk_id':10})
        self.assertFalse(other.is_connected())
        client.disconnect()

    def test_expiry_preserves_contiguous_paid_session(self):
        db.session.execute(text("UPDATE vendor_1_dashboard SET end_time=:end"), {'end':self.start.time()})
        db.session.execute(text("UPDATE vendor_1_dashboard SET date=:day,start_time=:start"), {'day':(self.start-timedelta(minutes=20)).date(),'start':(self.start-timedelta(minutes=20)).time()})
        db.session.execute(text("INSERT INTO bookings VALUES(6,100,1,'checked_in','{}')"))
        db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES(6,77,'Player',100,10,:day,:start,:end,'current')"),
                           {'day':self.start.date(),'start':self.start.time(),'end':self.end.time()})
        db.session.commit()
        self.assertEqual(runtime['expire_vendor'](1),0)
        self.assertFalse(db.session.execute(text('SELECT is_available FROM vendor_1_console_availability WHERE console_id=10')).scalar_one())
        self.assertEqual(runtime['booking_window'](1,5,10)['status'],'active')

    def _follow_on(self, bid, status='confirmed', user=77, console=-1, start=None, minutes=30):
        start = start or self.end
        end = start + timedelta(minutes=minutes)
        db.session.execute(text("INSERT INTO bookings(id,game_id,access_code_id,status,squad_details,user_id) VALUES(:b,100,NULL,:s,'{}',:u)"),
                           {'b': bid, 's': status, 'u': user})
        db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES(:b,:u,'Player',100,:c,:day,:start,:end,'upcoming')"),
                           {'b': bid, 'u': user, 'c': console, 'day': start.date(), 'start': start.time(), 'end': end.time()})
        db.session.commit()
        return end

    def test_next_slot_bought_later_joins_running_session(self):
        end = self._follow_on(6)
        runtime['expire_vendor'](1)
        row = db.session.execute(text("SELECT d.book_status, d.console_id, b.status, b.squad_details FROM vendor_1_dashboard d JOIN bookings b ON b.id=d.book_id WHERE d.book_id=6")).one()
        self.assertEqual((row.book_status, row.console_id, row.status), ('current', 10, 'checked_in'))
        self.assertEqual(row.squad_details['assigned_console_ids'], [10])
        window = runtime['booking_window'](1, 5, 10)
        self.assertEqual(window['booking_ids'], [5, 6])
        _, expected_end = runtime['utc_window'](end.date(), self.end.time(), end.time())
        self.assertEqual(window['end_time'], expected_end.isoformat())
        self.assertGreater(window['seconds_remaining'], 2900)

    def test_chain_of_follow_ons_and_restart_is_idempotent(self):
        mid = self._follow_on(6)
        self._follow_on(7, start=mid)
        runtime['expire_vendor'](1)
        runtime['expire_vendor'](1)
        self.assertEqual(runtime['booking_window'](1, 5, 10)['booking_ids'], [5, 6, 7])

    def test_follow_on_not_joined_when_unaccepted_elsewhere_or_other_gamer(self):
        db.session.execute(text("INSERT INTO users VALUES(78,'Other')"))
        db.session.commit()
        self._follow_on(6, status='pending_acceptance')
        self._follow_on(7, console=11)
        self._follow_on(8, user=78)
        self._follow_on(9, start=self.end + timedelta(minutes=5))  # gap: a new visit
        runtime['expire_vendor'](1)
        states = dict(db.session.execute(text("SELECT book_id, book_status FROM vendor_1_dashboard WHERE book_id>5")).all())
        self.assertEqual(states, {6: 'upcoming', 7: 'upcoming', 8: 'upcoming', 9: 'upcoming'})
        self.assertEqual(runtime['booking_window'](1, 5, 10)['booking_ids'], [5])

    def test_stale_session_is_not_stretched(self):
        old = self.start - timedelta(hours=3)
        db.session.execute(text("UPDATE vendor_1_dashboard SET date=:d,start_time=:s,end_time=:e WHERE book_id=5"),
                           {'d': old.date(), 's': old.time(), 'e': (old + timedelta(minutes=30)).time()})
        db.session.commit()
        self._follow_on(6, start=old + timedelta(minutes=30), minutes=240)
        runtime['expire_vendor'](1)
        self.assertEqual(db.session.execute(text("SELECT book_status FROM vendor_1_dashboard WHERE book_id=6")).scalar(), 'upcoming')

    def test_follow_on_stretches_enrolled_pc_session(self):
        from types import SimpleNamespace
        end = self._follow_on(6)
        db.session.execute(text('CREATE TABLE kiosk_runtime_sessions(id text, vendor_id integer, console_id integer, ended_at timestamp)'))
        db.session.commit()
        _, old_end = runtime['utc_window'](self.start.date(), self.start.time(), self.end.time())
        naive = old_end.astimezone(timezone.utc).replace(tzinfo=None)
        managed = SimpleNamespace(id='r1', paid_until=naive, reserved_until=naive, booking_ids=[5], stop_at=None,
                                  status='overtime_pending', reason='staff_resolution_required', notice_boundary=naive)
        query = Mock()
        query.filter_by.return_value.populate_existing.return_value.with_for_update.return_value.first.return_value = managed
        self.extensions.RuntimeSession = SimpleNamespace(query=query)
        self.extensions.changed = Mock()
        runtime['expire_vendor'](1)
        _, expected = runtime['utc_window'](end.date(), self.end.time(), end.time())
        expected = expected.astimezone(timezone.utc).replace(tzinfo=None)
        self.assertEqual((managed.reserved_until, managed.paid_until, managed.booking_ids), (expected, expected, [5, 6]))
        self.assertEqual((managed.status, managed.reason, managed.notice_boundary), ('active', None, None))
        self.extensions.changed.assert_called_once_with(managed)
        # A paid auto-continue already past the slot end is never overlapped.
        managed.reserved_until = expected + timedelta(minutes=30)
        self.extensions.changed.reset_mock()
        runtime['_stretch_runtime'](1, 10, 77, expected, expected + timedelta(minutes=30), [7])
        self.extensions.changed.assert_not_called()

    def test_link_token_and_scope(self):
        with self.app.test_request_context(headers={'Authorization':'Bearer link-a'}):
            ident = security['runtime_identity']()
            self.assertEqual(ident['console_id'], 10)
            for args in ((2,20,200),(1,11,100),(1,10,200)):
                with self.assertRaises(security['KioskError']): security['check_scope'](ident,*args)
        self.assertEqual(self.post('/release/100/10/1', {'booking_id':5}, token='bad').status_code,401)

    def test_expired_and_user_jwt_rejected(self):
        for subject, expiry, code in [({'id':1,'type':'vendor'},-1,'token_expired'), ({'id':1,'type':'user'},600,'vendor_token_required')]:
            token = jwt.encode({'sub':subject,'exp':datetime.now(timezone.utc)+timedelta(seconds=expiry)},self.app.config['JWT_SECRET_KEY'])
            result = self.post('/release/100/10/1', {'booking_id':5}, token=token)
            self.assertEqual(result.json['code'],code)

    def test_remaining_uses_server_time_and_utc(self):
        result = runtime['booking_window'](1,5,10)
        self.assertEqual(result['status'],'active')
        self.assertTrue(result['end_time'].endswith('+00:00'))
        self.assertLessEqual(result['seconds_remaining'],1200)
        self.assertGreater(result['seconds_remaining'],1180)
        with self.assertRaises(security['KioskError']): runtime['booking_window'](1,5,11)

    def test_overnight_and_invalid_window(self):
        start,end = runtime['utc_window'](date(2026,9,22),time(23,30),time(0,30))
        self.assertEqual((end-start).total_seconds(),3600)
        with self.assertRaises(security['KioskError']): runtime['utc_window'](date(2026,9,22),time(10),time(10))

    def test_idempotency_replay_and_conflict(self):
        first = self.post('/release/100/10/1',{'booking_id':5},key='once')
        second = self.post('/release/100/10/1',{'booking_id':5},key='once')
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.json,second.json)
        self.assertEqual(self.calls,1)
        self.assertEqual(self.post('/release/100/10/1',{'booking_id':6},key='once').status_code,409)

    def test_scheduled_end_continues_overtime_until_release_or_cancel(self):
        db.session.execute(text("UPDATE vendor_1_dashboard SET end_time=:end"), {'end':(self.start+timedelta(seconds=10)).time()})
        db.session.commit()
        self.assertEqual(runtime['expire_vendor'](1),0)
        self.assertFalse(db.session.execute(text('SELECT is_available FROM vendor_1_console_availability WHERE console_id=10')).scalar_one())
        window=runtime['booking_window'](1,5,10)
        self.assertEqual(window['status'],'active')
        self.assertGreater(window['overtime_seconds'],0)
        self.assertFalse(window['auto_lock_at_end'])
        db.session.execute(text("UPDATE bookings SET status='cancelled' WHERE id=5"))
        db.session.commit()
        self.assertEqual(runtime['expire_vendor'](1),1)
        self.assertEqual(runtime['booking_window'](1,5,10)['status'],'cancelled')


    def test_dashboard_assignment_notifies_only_on_success(self):
        body = dict(vendor_id=1,game_id=100,console_id=10,booking_ids=[5])
        with patch.dict(security, vendor_identity=lambda token: {'kind':'vendor','vendor_id':1},
                        check_scope=lambda *args: None):
            failed = self.post('/assign',dict(body,fail=True))
            self.assertEqual(failed.status_code,409)
            self.ws._emit_to_kiosk.assert_not_called()
            success = self.post('/assign',body)
            self.assertEqual(success.status_code,200)
            self.ws._emit_to_kiosk.assert_called_once()
            self.assertEqual(self.ws._emit_to_kiosk.call_args.args[:2],(10,'unlock_request'))

    def test_dashboard_state_unlocks_each_assigned_squad_pc(self):
        db.session.execute(text("UPDATE bookings SET squad_details=' {\"assigned_console_ids\":[10,11]}'::jsonb WHERE id=5"))
        db.session.commit()
        with self.app.test_request_context():
            runtime['notify_console_runtime'](1, [10,11])
        calls = self.ws._emit_to_kiosk.call_args_list
        self.assertEqual([c.args[:2] for c in calls], [(10,'unlock_request'),(11,'unlock_request')])
        self.assertTrue(all(c.args[2]['status']=='active' for c in calls))

    def test_partial_release_locks_only_released_squad_pc(self):
        db.session.execute(text("UPDATE bookings SET squad_details=' {\"assigned_console_ids\":[11],\"released_console_ids\":[10]}'::jsonb WHERE id=5"))
        db.session.commit()
        with self.app.test_request_context():
            runtime['notify_console_runtime'](1, [10,11])
        self.assertEqual([c.args[:2] for c in self.ws._emit_to_kiosk.call_args_list],
                         [(10,'session_expired'),(11,'unlock_request')])

    def test_upstream_started_booking_unlocks_but_never_locks(self):
        db.session.execute(text("UPDATE bookings SET squad_details=' {\"assigned_console_ids\":[11],\"released_console_ids\":[10]}'::jsonb WHERE id=5"))
        db.session.commit()
        with self.app.test_request_context():
            runtime['notify_console_runtime'](1, [10,11], unlock_only=True)
        self.assertEqual([c.args[:2] for c in self.ws._emit_to_kiosk.call_args_list],
                         [(11,'unlock_request')])

    def test_release_notifies_lock_after_commit(self):
        result = self.post('/release/100/10/1', {'booking_id':5})
        self.assertEqual(result.status_code,200)
        self.ws._emit_to_kiosk.assert_called_once()
        self.assertEqual(self.ws._emit_to_kiosk.call_args.args[:2],(10,'session_expired'))
        self.assertEqual(db.session.execute(text('SELECT book_status FROM vendor_1_dashboard WHERE book_id=5')).scalar(),'completed')

    def test_code_bound_to_console_and_single_use_after_end(self):
        first = self.post('/start',{'console_id':10,'access_code':'123456'})
        self.assertEqual(first.status_code,200,first.json)
        self.assertEqual(first.json['data']['user_name'],'Player')
        self.assertEqual(self.post('/start',{'console_id':11,'access_code':'123456'},token='link-b').status_code,409)
        self.assertEqual(self.post('/start',{'console_id':10,'access_code':'123456'}).status_code,200)
        db.session.execute(text("UPDATE vendor_1_dashboard SET book_status='completed' WHERE book_id=5"))
        db.session.commit()
        self.assertEqual(self.post('/start',{'console_id':10,'access_code':'123456'}).status_code,409)

    def test_failed_start_rolls_back_redemption_and_mutation(self):
        result = self.post('/start',{'console_id':10,'access_code':'123456','fail':True})
        self.assertEqual(result.status_code,500)
        self.assertEqual(db.session.execute(text('SELECT count(*) FROM kiosk_code_redemptions')).scalar_one(),0)
        self.assertEqual(db.session.execute(text('SELECT book_status FROM vendor_1_dashboard WHERE book_id=5')).scalar_one(),'current')

    def test_code_cannot_be_bypassed_with_booking_id(self):
        self.assertEqual(self.post('/start',{'console_id':10,'booking_id':5}).status_code,400)
        self.assertEqual(self.post('/start',{'console_id':10,'access_code':'123456','vendor_id':2}).status_code,403)
        self.assertEqual(self.post('/start',{'console_id':10,'access_code':'123456'},token='').status_code,401)

    def test_rate_limit_persists_on_failures(self):
        for _ in range(10):
            self.assertEqual(self.post('/start',{'console_id':10,'access_code':'000000'}).status_code,404)
        self.assertEqual(self.post('/start',{'console_id':10,'access_code':'000000'}).status_code,429)

    def test_unlink_requires_token_and_matching_identity(self):
        self.assertEqual(self.post('/unlink',{'console_id':10}).status_code,401)
        self.assertEqual(self.post('/unlink',{'session_token':'link-a','console_id':11}).status_code,403)
        self.assertEqual(self.post('/unlink',{'session_token':'link-a','console_id':10,'vendor_id':1,'kiosk_id':'machine-a'}).status_code,200)
        self.assertEqual(self.post('/release/100/10/1',{'booking_id':5}).status_code,401)


if __name__ == '__main__':
    unittest.main()
