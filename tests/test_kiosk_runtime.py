"""Run with KIOSK_TEST_DATABASE_URL pointing to a disposable PostgreSQL DB.

Loads production functions without application boot/upstream connections. Each test
uses a fresh schema; no production credentials or data are used.
"""
import ast
from datetime import datetime, timedelta, timezone, date, time
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
                INSERT INTO console_link_sessions VALUES(1,10,1,'machine-a','link-a','active',NULL,NULL),(2,11,1,'machine-b','link-b','active',NULL,NULL),(3,20,2,'machine-c','link-c','active',NULL,NULL);
                INSERT INTO vendor_1_console_availability VALUES(10,100,FALSE),(11,100,TRUE);
            '''))
            # Migration is idempotent and actually executed against PostgreSQL.
            migration = (ROOT / 'sql/20260922_kiosk_runtime.sql').read_text().replace('BEGIN;', '').replace('COMMIT;', '')
            conn.execute(text(migration))
            conn.execute(text(migration))
        now = datetime.now(runtime['IST']).replace(tzinfo=None)
        self.start = now - timedelta(minutes=1)
        self.end = now + timedelta(minutes=20)
        db.session.execute(text('INSERT INTO vendor_1_dashboard VALUES(5,77,\'Player\',100,10,:day,:start,:end,\'current\')'),
                           dict(day=self.start.date(), start=self.start.time(), end=self.end.time()))
        db.session.commit()
        self.calls = 0
        fake_routes = ModuleType('app.routes')
        fake_routes._invalidate_vendor_caches = Mock()
        fake_ws = ModuleType('app.services.websocket_service')
        fake_ws._emit_to_kiosk = Mock()
        fake_ws.socketio = Mock()
        fake_security = ModuleType('app.services.kiosk_security')
        fake_security.__dict__.update(security)
        fake_runtime = ModuleType('app.services.kiosk_runtime')
        fake_runtime.__dict__.update(runtime)
        self.modules = patch.dict(sys.modules, {'app.routes': fake_routes,
            'app.services.websocket_service': fake_ws, 'app.services.kiosk_runtime': fake_runtime,
            'app.services.kiosk_security': fake_security})
        self.modules.start()
        self.ws = fake_ws
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
            db.session.execute(text("UPDATE vendor_1_dashboard SET book_status='current' WHERE book_id=5"))
            return jsonify(booking_ids=[5]), 200
        # Execute actual unlink route body with no application bootstrap.
        tree = ast.parse((ROOT/'app/routes.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'kiosk_unlink')
        fn.decorator_list = []
        scope = dict(request=request, db=db, text=text, jsonify=jsonify,
                     _invalidate_vendor_caches=Mock())
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<unlink>', 'exec'), scope)
        self.app.add_url_rule('/unlink', view_func=scope['kiosk_unlink'], methods=['POST'])
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

    def test_real_assignment_starts_booking_in_same_transaction_as_redemption(self):
        from sqlalchemy.ext.automap import automap_base
        from flask import current_app
        db.session.execute(text("ALTER TABLE consoles ADD COLUMN console_number integer DEFAULT 1, ADD COLUMN model_number text DEFAULT 'PC'"))
        db.session.execute(text("UPDATE vendor_1_dashboard SET book_status='upcoming', console_id=NULL WHERE book_id=5"))
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
                     ('_booking_start_eligibility','_assign_console_to_multiple_bookings_core','kiosk_start_session')]
        for fn in tree.body: fn.decorator_list=[]
        scope = dict(db=db,text=text,request=request,jsonify=jsonify,current_app=current_app,g=g,
                     datetime=datetime,date=date,timedelta=timedelta,IST=runtime['IST'],dt_timezone=timezone,
                     _resolve_console_group_from_name=lambda *a,**k:'pc',_invalidate_vendor_caches=Mock(),
                     KIOSK_GRACE_MIN=0,_emit_to_kiosk=Mock(),**models)
        exec(compile(tree,'<production kiosk start>','exec'),scope)
        with self.app.test_request_context('/start',method='POST',json={'console_id':10,'access_code':'123456'},
                                          headers={'Authorization':'Bearer link-a'}):
            # Notification formatting is unrelated to the transaction; missing optional
            # fixture columns are intentionally logged by the production emitter.
            with patch.object(self.app.logger,'exception'):
                result = self.app.make_response(runtime['secure_start'](scope['kiosk_start_session'])())
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(result.json['data']['status'],'active')
        self.assertEqual(db.session.execute(text('SELECT console_id FROM kiosk_code_redemptions')).scalar_one(),10)
        self.assertEqual(db.session.execute(text('SELECT book_status FROM vendor_1_dashboard')).scalar_one(),'current')
        self.assertFalse(db.session.execute(text('SELECT is_available FROM vendor_1_console_availability WHERE console_id=10')).scalar_one())

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
        db.session.execute(text("UPDATE vendor_1_dashboard SET start_time=:start"), {'start':(self.start-timedelta(minutes=20)).time()})
        db.session.execute(text("INSERT INTO bookings VALUES(6,100,1,'checked_in','{}')"))
        db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES(6,77,'Player',100,10,:day,:start,:end,'current')"),
                           {'day':self.start.date(),'start':self.start.time(),'end':self.end.time()})
        db.session.commit()
        self.assertEqual(runtime['expire_vendor'](1),1)
        self.assertFalse(db.session.execute(text('SELECT is_available FROM vendor_1_console_availability WHERE console_id=10')).scalar_one())
        self.assertEqual(runtime['booking_window'](1,5,10)['status'],'active')

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

    def test_expiry_without_client_and_cancelled(self):
        db.session.execute(text("UPDATE vendor_1_dashboard SET end_time=:end"), {'end':(self.start+timedelta(seconds=10)).time()})
        db.session.commit()
        self.assertEqual(runtime['expire_vendor'](1),1)
        self.assertTrue(db.session.execute(text('SELECT is_available FROM vendor_1_console_availability WHERE console_id=10')).scalar_one())
        self.assertEqual(runtime['booking_window'](1,5,10)['status'],'expired')
        self.assertEqual(runtime['expire_vendor'](1),0)
        db.session.execute(text("UPDATE bookings SET status='cancelled' WHERE id=5"))
        db.session.commit()
        self.assertEqual(runtime['booking_window'](1,5,10)['status'],'cancelled')

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
