"""Cross-flow capacity regressions against isolated PostgreSQL schemas."""
import ast
import importlib.util
import sys
import threading
import types
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, time
from pathlib import Path
from typing import Optional

import pytest
from flask import current_app, g
from sqlalchemy import text
from test_cafe_wallet import env, fund, seed_booking

ROOT = Path(__file__).resolve().parents[1]


def load_source(monkeypatch, name, path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules,name,module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def flows(env,monkeypatch):
    e = env
    if not e.pg:
        pytest.skip('Requires PostgreSQL row locks')
    services = types.ModuleType('services'); services.__path__=[]
    monkeypatch.setitem(sys.modules,'services',services)
    capacity = load_source(monkeypatch,'services.slot_capacity',ROOT.parent/'hfg-booking/services/slot_capacity.py')
    class Booking(e.db.Model):
        __tablename__='bookings'
        id=e.db.Column(e.db.Integer,primary_key=True)
        slot_id=e.db.Column(e.db.Integer)
        game_id=e.db.Column(e.db.Integer)
        user_id=e.db.Column(e.db.Integer)
        booking_mode=e.db.Column(e.db.String)
        squad_details=e.db.Column(e.db.JSON)
        status=e.db.Column(e.db.String)
        created_at=e.db.Column(e.db.DateTime)
    tree=ast.parse((ROOT.parent/'hfg-booking/services/booking_service.py').read_text())
    cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='BookingService')
    method=next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name=='create_booking')
    namespace=dict(db=e.db,g=g,current_app=current_app,uuid=uuid,text=text,Booking=Booking,
                   datetime=datetime,date=date,Optional=Optional,emit_booking_event=lambda *a,**kw:None)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='BookingService',bases=[],keywords=[],body=[method],decorator_list=[])],type_ignores=[])),str(ROOT.parent/'hfg-booking/services/booking_service.py'),'exec'),namespace)
    e.create = namespace['BookingService'].create_booking
    e.capacity = capacity
    with e.app.app_context():
        fund(e)
        e.db.session.execute(text('ALTER TABLE available_games ADD COLUMN total_slot integer DEFAULT 2'))
        e.db.session.execute(text('ALTER TABLE transactions ADD COLUMN booked_date date'))
        e.db.session.commit()
    return e


def first_slot(e):
    from app.services.cafe_slot_reservations import scheduled_slots, local_window
    now=datetime.utcnow()
    start,end=local_window(now,now+timedelta(minutes=60,seconds=45))
    return scheduled_slots(e.db.session.get(e.Link,1),start,end)[0]


def test_three_booking_flows_compete_for_same_last_unit(flows):
    e=flows
    with e.app.app_context():
        slot=first_slot(e)
        e.db.session.execute(text('UPDATE vendor_1_slot SET available_slot=1'))
        e.db.session.commit()
    barrier=threading.Barrier(3)
    def book(kind):
        with e.app.app_context():
            barrier.wait()
            try:
                if kind=='qr':
                    e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'cross-flow-qr',expected_amount=10000)
                else:
                    e.create(slot['slot_id'],100,2,None,slot['date'],emit_events=(kind=='app'),commit=(kind=='app'))
                e.db.session.commit()
                return 'reserved'
            except (ValueError,e.s.CafeError):
                e.db.session.rollback()
                return 'unavailable'
    with ThreadPoolExecutor(3) as pool:
        outcomes=list(pool.map(book,['app','dashboard','qr']))
    assert outcomes.count('reserved')==1
    with e.app.app_context():
        assert e.db.session.execute(text('SELECT available_slot FROM vendor_1_slot WHERE slot_id=:slot AND date=:day'),
            {'slot':slot['slot_id'],'day':slot['date']}).scalar()==0
        assert e.db.session.execute(text('SELECT MIN(available_slot) FROM vendor_1_slot')).scalar()>=0


def test_qr_reservation_retry_failure_and_completion_release_once(flows):
    e=flows
    with e.app.app_context():
        session=e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'qr-capacity-retry',expected_amount=10000)
        e.db.session.commit()
        holds=e.m.CafeSlotReservation.query.filter_by(session_id=session.id).all()
        assert len(holds)>=3  # Partial first/last slots and acknowledgement buffer.
        assert e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'qr-capacity-retry').id==session.id
        e.db.session.commit()
        assert e.m.CafeSlotReservation.query.count()==len(holds)
        assert e.db.session.execute(text('SELECT MIN(available_slot) FROM vendor_1_slot')).scalar()==1
        e.s.acknowledge(session.id,e.db.session.get(e.Link,1),session.command_token,False)
        e.db.session.commit()
        e.s.acknowledge(session.id,e.db.session.get(e.Link,1),session.command_token,False)
        e.db.session.commit()
        assert e.db.session.execute(text('SELECT MIN(available_slot) FROM vendor_1_slot')).scalar()==2
        assert all(r.released_at for r in e.m.CafeSlotReservation.query.all())
        active=e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'qr-capacity-complete')
        e.db.session.commit()
        e.s.acknowledge(active.id,e.db.session.get(e.Link,1),active.command_token,True)
        e.db.session.commit()
        active.ends_at=datetime.utcnow()-timedelta(seconds=1)
        e.db.session.commit()
        e.s.expire_sessions();e.s.expire_sessions()
        # Funded time ending does not free a PC while the gamer continues.
        assert active.state == 'active'
        assert e.db.session.execute(text('SELECT MIN(available_slot) FROM vendor_1_slot')).scalar()==1
        from app.services.cafe_slot_reservations import release_slots
        release_slots(active)
        release_slots(active)
        e.db.session.commit()
        assert e.db.session.execute(text('SELECT MIN(available_slot) FROM vendor_1_slot')).scalar()==2


def test_qr_multislot_conflict_rolls_back_wallet_and_all_slots(flows):
    e=flows
    with e.app.app_context():
        from app.services.cafe_slot_reservations import scheduled_slots,local_window
        now=datetime.utcnow();start,end=local_window(now,now+timedelta(minutes=60,seconds=45))
        rows=scheduled_slots(e.db.session.get(e.Link,1),start,end)
        later=rows[-1]
        e.db.session.execute(text('UPDATE vendor_1_slot SET available_slot=0,is_available=false WHERE slot_id=:slot AND date=:day'),
            {'slot':later['slot_id'],'day':later['date']})
        e.db.session.commit()
        with pytest.raises(e.s.CafeError):
            e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'qr-full-later-slot')
        e.db.session.rollback()
        assert e.m.CafeSlotReservation.query.count()==0
        assert e.db.session.get(e.m.CafeWallet,(1,1)).reserved==0
        assert e.db.session.execute(text('SELECT available_slot FROM vendor_1_slot WHERE slot_id=:slot AND date=:day'),
            {'slot':rows[0]['slot_id'],'day':rows[0]['date']}).scalar()==2


def test_desk_failed_payment_rolls_back_capacity_and_booking(flows):
    e=flows
    with e.app.app_context():
        slot=first_slot(e)
        e.create(slot['slot_id'],100,2,None,slot['date'],emit_events=False,commit=False)
        e.db.session.rollback()  # e.g. pass validation fails before desk commit.
        assert e.db.session.execute(text('SELECT count(*) FROM bookings')).scalar()==0
        assert e.db.session.execute(text('SELECT MIN(available_slot) FROM vendor_1_slot')).scalar()==2


def test_future_assignment_and_qr_reservation_cannot_overlap(flows):
    e=flows
    from app.services.cafe_slot_reservations import local_window
    with e.app.app_context():
        start,end=local_window(datetime.utcnow()+timedelta(minutes=20),datetime.utcnow()+timedelta(minutes=50))
        e.db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES(1,'upcoming',999,:day,:start,:end)"),
            {'day':start.date(),'start':start.time(),'end':end.time()})
        e.db.session.commit()
        with pytest.raises(e.s.CafeError,match='another booking'):
            e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'qr-future-conflict')
        e.db.session.rollback()
        e.db.session.execute(text('DELETE FROM vendor_1_dashboard'));e.db.session.commit()
        session=e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'qr-before-future')
        e.db.session.commit()
        with pytest.raises(Exception,match='claimed by a QR'):
            e.db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES(1,'upcoming',999,:day,:start,:end)"),
                {'day':start.date(),'start':start.time(),'end':end.time()})
        e.db.session.rollback()
        # Non-overlapping future bookings remain valid.
        start,end=local_window(datetime.utcnow()+timedelta(hours=3),datetime.utcnow()+timedelta(hours=4))
        e.db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES(1,'upcoming',1000,:day,:start,:end)"),
            {'day':start.date(),'start':start.time(),'end':end.time()})
        e.db.session.commit()


def test_starting_paid_booking_does_not_consume_capacity_again(flows):
    e=flows
    with e.app.app_context():
        seed_booking(e)
        before=e.db.session.execute(text('SELECT SUM(available_slot) FROM vendor_1_slot')).scalar()
        session=e.b.reserve_booking(e.db.session.get(e.Link,1),1,101,'paid-qr-capacity')
        e.db.session.commit()
        from app.services.cafe_slot_reservations import local_window
        start,end=local_window(datetime.utcnow()+timedelta(minutes=1),datetime.utcnow()+timedelta(minutes=5))
        with pytest.raises(Exception,match='claimed by a QR'):
            e.db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES(1,'upcoming',999,:day,:start,:end)"),
                {'day':start.date(),'start':start.time(),'end':end.time()})
        e.db.session.rollback()
        e.s.acknowledge(session.id,e.db.session.get(e.Link,1),session.command_token,True)
        e.db.session.commit()
        assert e.m.CafeSlotReservation.query.count()==0
        assert e.db.session.execute(text('SELECT SUM(available_slot) FROM vendor_1_slot')).scalar()==before


def test_reconciliation_preserves_pending_squad_and_qr_capacity(flows):
    e=flows
    tree=ast.parse((ROOT.parent/'hfg-onboard/services/services.py').read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='VendorService')
    node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='reconcile_vendor_slot_capacity_window')
    namespace=dict(db=e.db,text=text)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='VendorService',bases=[],keywords=[],body=[node],decorator_list=[])],type_ignores=[])),str(ROOT.parent/'hfg-onboard/services/services.py'),'exec'),namespace)
    with e.app.app_context():
        slot=first_slot(e)
        e.db.session.execute(text('UPDATE available_games SET total_slot=4'));e.db.session.execute(text('UPDATE vendor_1_slot SET available_slot=4'));e.db.session.commit()
        booking=e.create(slot['slot_id'],100,2,None,slot['date'],slot_units=2,emit_events=False,commit=False)
        e.db.session.commit()
        session=e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'qr-reconcile-capacity')
        e.db.session.commit()
        namespace['VendorService'].reconcile_vendor_slot_capacity_window(1,slot['date'],slot['date'])
        e.db.session.commit()
        assert e.db.session.execute(text('SELECT available_slot FROM vendor_1_slot WHERE slot_id=:slot AND date=:day'),
            {'slot':slot['slot_id'],'day':slot['date']}).scalar()==1
        assert e.db.session.get(e.m.CafeWallet,(1,1)).reserved==10000


def test_shared_slot_helpers_match_across_services():
    content=(ROOT/'app/services/slot_capacity.py').read_bytes()
    assert content==(ROOT.parent/'hfg-booking/services/slot_capacity.py').read_bytes()
    assert content==(ROOT.parent/'hfg-background-processor/slot_capacity.py').read_bytes()


def test_legacy_assignments_compete_for_same_console_interval(flows):
    e=flows
    from app.services.cafe_slot_reservations import local_window
    start,end=local_window(datetime.utcnow()+timedelta(hours=2),datetime.utcnow()+timedelta(hours=3))
    barrier=threading.Barrier(2)
    def assign(bid):
        with e.app.app_context():
            barrier.wait()
            try:
                e.db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES(1,'upcoming',:bid,:day,:start,:end)"),
                    {'bid':bid,'day':start.date(),'start':start.time(),'end':end.time()})
                e.db.session.commit()
                return True
            except Exception as error:
                e.db.session.rollback()
                assert 'already has a booking' in str(error)
                return False
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(assign,[901,902]))==[False,True]


def test_migration_backfills_live_qr_holds_and_recovers_old_completion(flows):
    e=flows
    def migrate():
        raw=e.db.engine.raw_connection()
        try:
            raw.cursor().execute((ROOT/'sql/20261002_shared_slot_reservations.sql').read_text());raw.commit()
        finally:
            raw.close()
    with e.app.app_context():
        session=e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'qr-rollout-live')
        e.db.session.commit()
        e.s.acknowledge(session.id,e.db.session.get(e.Link,1),session.command_token,True)
        e.db.session.commit()
        # Represent the old deployment: wallet paid and PC busy, no dated holds.
        e.db.session.execute(text('UPDATE vendor_1_slot v SET available_slot=available_slot+1 WHERE EXISTS (SELECT 1 FROM cafe_slot_reservations r WHERE r.vendor_id=v.vendor_id AND r.date=v.date AND r.slot_id=v.slot_id)'))
        e.db.session.execute(text('DELETE FROM cafe_slot_reservations'));e.db.session.commit()
        migrate();migrate()
        assert e.db.session.execute(text('SELECT MIN(available_slot) FROM vendor_1_slot')).scalar()==1
        assert e.m.CafeSlotReservation.query.count()>=3
        # An old worker may complete this session before new workers roll out.
        e.db.session.execute(text("UPDATE cafe_play_sessions SET state='completed',console_claim=NULL WHERE id=:id"),{'id':session.id})
        e.db.session.commit()
        e.s.expire_sessions();e.s.expire_sessions()
        assert e.db.session.execute(text('SELECT MIN(available_slot) FROM vendor_1_slot')).scalar()==2
        assert e.m.CafeSlotReservation.query.filter_by(released_at=None).count()==0


def test_qr_overnight_holds_use_both_dates(flows,monkeypatch):
    e=flows
    from app.services.cafe_slot_reservations import IST
    from datetime import timezone
    local=datetime.now(IST).replace(hour=23,minute=50,second=0,microsecond=0)
    fixed=local.astimezone(timezone.utc).replace(tzinfo=None)
    class Clock(datetime):
        @classmethod
        def utcnow(cls):
            return fixed
    monkeypatch.setattr(e.s,'datetime',Clock)
    with e.app.app_context():
        session=e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'qr-overnight-capacity')
        e.db.session.commit()
        days={r.date for r in e.m.CafeSlotReservation.query.filter_by(session_id=session.id)}
        assert days=={local.date(),local.date()+timedelta(days=1)}
        e.s.acknowledge(session.id,e.db.session.get(e.Link,1),session.command_token,False)
        e.db.session.commit()
        assert e.db.session.execute(text('SELECT MIN(available_slot) FROM vendor_1_slot')).scalar()==2


def test_reschedule_moves_only_reserved_units_and_updates_canonical_date(flows,monkeypatch):
    e=flows
    move=load_source(monkeypatch,'services.upcoming_slots',ROOT.parent/'hfg-booking/services/upcoming_slots.py').move_slot
    controllers=types.ModuleType('controllers');controllers.__path__=[]
    monkeypatch.setitem(sys.modules,'controllers',controllers)
    monkeypatch.setitem(sys.modules,'controllers.booking_controller',types.SimpleNamespace(_requires_multi_console_units=lambda *args:True))
    from app.services.cafe_slot_reservations import IST
    today=datetime.now(IST).date();tomorrow=today+timedelta(days=1)
    with e.app.app_context():
        booking=e.create(110,100,2,None,today,slot_units=2,emit_events=False,commit=False)
        booking.status='confirmed'
        e.db.session.execute(text("INSERT INTO transactions(id,booking_id,vendor_id,user_id,booking_type,amount,settlement_status,booked_date) VALUES(901,:id,1,2,'booking',100,'completed',:day)"),{'id':booking.id,'day':today})
        e.db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES(NULL,'upcoming',:id,:day,:start,:end)"),{'id':booking.id,'day':today,'start':time(5),'end':time(5,30)})
        e.db.session.commit()
        # The test clock is before this source slot, regardless of real time.
        move(e.db.session,1,booking.id,111,tomorrow,datetime.combine(today,time(4)))
        e.db.session.commit()
        details=e.db.session.execute(text('SELECT squad_details FROM bookings WHERE id=:id'),{'id':booking.id}).scalar()
        assert details['booked_date']==tomorrow.isoformat() and details['slot_units']==2
        assert e.db.session.execute(text('SELECT available_slot FROM vendor_1_slot WHERE slot_id=110 AND date=:day'),{'day':today}).scalar()==2
        assert e.db.session.execute(text('SELECT available_slot FROM vendor_1_slot WHERE slot_id=111 AND date=:day'),{'day':tomorrow}).scalar()==0
        assert e.db.session.execute(text('SELECT available_slot FROM vendor_1_slot WHERE slot_id=112 AND date=:day'),{'day':tomorrow}).scalar()==2


def test_background_release_is_concurrent_safe_and_preserves_squad_units(flows,monkeypatch):
    e=flows
    monkeypatch.setitem(sys.modules,'slot_capacity',e.capacity)
    tree=ast.parse((ROOT.parent/'hfg-background-processor/tasks.py').read_text())
    method=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='release_slot_task')
    method.decorator_list=[]
    class Game(e.db.Model):
        __tablename__='available_games'
        id=e.db.Column(e.db.Integer,primary_key=True)
        vendor_id=e.db.Column(e.db.Integer)
    namespace=dict(SessionLocal=e.db.session,Booking=e.create.__globals__['Booking'],AvailableGame=Game,datetime=datetime)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(ROOT.parent/'hfg-background-processor/tasks.py'),'exec'),namespace)
    from app.services.cafe_slot_reservations import IST
    today=datetime.now(IST).date();tomorrow=today+timedelta(days=1)
    with e.app.app_context():
        booking=e.create(110,100,2,None,tomorrow,slot_units=2,emit_events=False,commit=False)
        bid=booking.id;e.db.session.commit()
    barrier=threading.Barrier(2)
    def expire(_):
        with e.app.app_context():
            barrier.wait()
            # Even a stale job date must use the booking's reserved date.
            namespace['release_slot_task'](110,bid,today)
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(expire,range(2)))
    with e.app.app_context():
        assert e.db.session.execute(text('SELECT status FROM bookings WHERE id=:id'),{'id':bid}).scalar()=='verification_failed'
        assert e.db.session.execute(text('SELECT available_slot FROM vendor_1_slot WHERE slot_id=110 AND date=:day'),{'day':tomorrow}).scalar()==2
        assert e.db.session.execute(text('SELECT MAX(available_slot) FROM vendor_1_slot')).scalar()==2


@pytest.fixture
def overtime_route(flows,monkeypatch):
    """Run the real overtime endpoint with unrelated mail/tax helpers stubbed."""
    e=flows
    from flask import request,jsonify
    User=sys.modules['app.models.user'].User
    monkeypatch.setattr(User,'contact_info',property(lambda self:types.SimpleNamespace(email='gamer@example.test')),raising=False)
    class Slot(e.db.Model):
        __tablename__='slots'
        id=e.db.Column(e.db.Integer,primary_key=True)
        gaming_type_id=e.db.Column(e.db.Integer)
        start_time=e.db.Column(e.db.Time)
        end_time=e.db.Column(e.db.Time)
    class Game(e.db.Model):
        __tablename__='available_games'
        id=e.db.Column(e.db.Integer,primary_key=True)
        vendor_id=e.db.Column(e.db.Integer)
        game_name=e.db.Column(e.db.String)
    class Transaction(e.db.Model):
        __tablename__='transactions'
        id=e.db.Column(e.db.Integer,primary_key=True)
        booking_id=e.db.Column(e.db.Integer)
        vendor_id=e.db.Column(e.db.Integer)
        user_id=e.db.Column(e.db.Integer)
        booked_date=e.db.Column(e.db.Date)
        booking_type=e.db.Column(e.db.String)
        amount=e.db.Column(e.db.Numeric)
        settlement_status=e.db.Column(e.db.String)
        def __init__(self,**values):
            for name,value in values.items():
                setattr(self,name,value)
    with e.app.app_context():
        e.db.session.execute(text('CREATE SEQUENCE overtime_tx_id'))
        e.db.session.execute(text("ALTER TABLE transactions ALTER COLUMN id SET DEFAULT nextval('overtime_tx_id')"))
        e.db.session.commit()
    monkeypatch.setitem(sys.modules,'services.payment_methods',types.SimpleNamespace(require_method=lambda *args:None))
    writes=[]
    class Inserts:
        @staticmethod
        def insert_into_vendor_dashboard_table(tx_id,console_id,*,commit):
            assert commit is False
            writes.append(tx_id)
        @staticmethod
        def insert_into_vendor_promo_table(tx_id,console_id,*,commit):
            assert commit is False
    tree=ast.parse((ROOT.parent/'hfg-booking/controllers/booking_controller.py').read_text())
    method=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='extra_booking');method.decorator_list=[]
    namespace=dict(db=e.db,g=g,request=request,jsonify=jsonify,current_app=current_app,text=text,
        User=User,Slot=Slot,AvailableGame=Game,Booking=e.create.__globals__['Booking'],Transaction=Transaction,
        BookingService=Inserts,datetime=datetime,
        resolve_transaction_actor=lambda *a,**k:dict(source_channel='dashboard',staff_id=1,staff_name='Desk',staff_role='owner'),
        normalize_payment_use_case=lambda *a:'cash',resolve_settlement_status=lambda *a:'completed',
        _resolve_console_group=lambda *a,**k:'pc',_requires_multi_console_units=lambda *a,**k:True,
        resolve_app_fee_amount=lambda *a,**k:0,
        calculate_gst_breakdown=lambda *a:dict.fromkeys(['taxable_amount','gst_rate','cgst_amount','sgst_amount','igst_amount','total_with_tax'],0),
        extra_booking_time_mail=lambda *a,**k:None,
        compute_booking_financial_summary=lambda *a:dict(amount_due=0,amount_paid=10,total_charged=10))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(ROOT.parent/'hfg-booking/controllers/booking_controller.py'),'exec'),namespace)
    e.app.add_url_rule('/test/overtime',view_func=namespace['extra_booking'],methods=['POST'])
    e.app.before_request(lambda:setattr(g,'vendor_id',1))
    return e,writes,namespace


def test_overtime_reuses_exact_date_without_duplicate_slot_hold(overtime_route):
    e,writes,namespace=overtime_route
    from app.services.cafe_slot_reservations import IST
    today=datetime.now(IST).date();tomorrow=today+timedelta(days=1)
    body=dict(consoleNumber=1,consoleType='pc',date=tomorrow.isoformat(),slotId=110,userId=2,
              username='Gamer',amount=10,gameId=100,modeOfPayment='cash',vendorId=1)
    with e.app.app_context():
        old=e.create(110,100,2,None,today,emit_events=False,commit=False)
        old.status='completed';e.db.session.commit()
        response=e.app.test_client().post('/test/overtime',json=body)
        assert response.status_code==201,response.json
        assert response.json['booking_id']!=old.id
        repeated=e.app.test_client().post('/test/overtime',json=body)
        assert repeated.status_code==201,repeated.json
        assert repeated.json['booking_id']==response.json['booking_id']
        assert len(writes)==1
        assert e.db.session.execute(text('SELECT available_slot FROM vendor_1_slot WHERE slot_id=110 AND date=:day'),{'day':tomorrow}).scalar()==1


def test_overtime_write_failure_rolls_back_new_capacity(overtime_route):
    e,writes,namespace=overtime_route
    from app.services.cafe_slot_reservations import IST
    day=datetime.now(IST).date()
    def fail(*args,**kwargs):
        raise RuntimeError('failed invoice insert')
    namespace['BookingService'].insert_into_vendor_promo_table=fail
    body=dict(consoleNumber=1,consoleType='pc',date=day.isoformat(),slotId=110,userId=2,
              username='Gamer',amount=10,gameId=100,modeOfPayment='cash',vendorId=1)
    with e.app.app_context():
        response=e.app.test_client().post('/test/overtime',json=body)
        assert response.status_code==500
        assert e.db.session.execute(text('SELECT count(*) FROM bookings')).scalar()==0
        assert e.db.session.execute(text('SELECT count(*) FROM transactions')).scalar()==0
        assert e.db.session.execute(text('SELECT MIN(available_slot) FROM vendor_1_slot')).scalar()==2


def test_unrelated_time_slots_can_book_while_qr_transaction_is_open(flows):
    e=flows
    from app.services.cafe_slot_reservations import IST
    future=datetime.now(IST)+timedelta(hours=4)
    slot_id=100+future.hour*2+(future.minute//30)
    ready=threading.Event();release=threading.Event()
    def qr_hold():
        with e.app.app_context():
            e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'qr-parallel-disjoint')
            ready.set()
            assert release.wait(10)
            e.db.session.commit()
    def other_booking():
        with e.app.app_context():
            e.create(slot_id,100,2,None,future.date(),emit_events=False,commit=False)
            e.db.session.commit()
    with ThreadPoolExecutor(2) as pool:
        qr=pool.submit(qr_hold)
        assert ready.wait(5)
        other=pool.submit(other_booking)
        try:
            other.result(timeout=5)
        finally:
            release.set()
        qr.result(timeout=5)
