"""Real PostgreSQL transactions: no money or slot updates are mocked."""
import sys
from datetime import datetime, timedelta
import pytest
from sqlalchemy import text
from test_cafe_wallet import env, fund, auth, staff_token


def engine(): return sys.modules['app.services.session_extensions']

def active(e,balance=20000):
    fund(e,amount=balance)
    qr=e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'extension-base-key')
    e.db.session.commit();e.s.acknowledge(qr.id,e.db.session.get(e.Link,1),qr.command_token,True);e.db.session.commit()
    # Funded boundary lies one minute ahead; next extension is quoted on real grid.
    now=datetime.utcnow()
    qr.ends_at=now.replace(second=0,microsecond=0)+timedelta(minutes=30-now.minute%30);e.db.session.commit()
    row=engine().attach(e.db.session.get(e.Link,1),{'kind':'self_qr','id':qr.id});e.db.session.commit()
    return row,qr

def extend(e,row,consent=True):
    c=engine();q,quote=c.quote(row);e.db.session.commit()
    body={'quote_id':q.id,'revision':row.revision,'idempotency_key':'extension-continue-key','credit_consent':consent}
    c.continue_session(row,q.id,body);e.db.session.commit()
    return q,body


def test_wallet_extension_holds_and_stop_refunds_unused(env):
    e=env
    with e.app.app_context():
        row,qr=active(e);q,body=extend(e,row)
        c=engine();w=e.db.session.get(e.m.CafeWallet,(1,1));reserved=w.reserved
        assert q.status=='granted' and reserved>0
        c.continue_session(row,q.id,body);e.db.session.commit()
        assert len(c.segments(row))==1 and w.reserved==reserved
        c.finish(row);e.db.session.commit()
        assert row.ended_at and w.reserved==0 and qr.state=='completed'
        assert c.snapshot(row)['billing']['amount_due_paise']==0
        assert e.m.CafeSlotReservation.query.filter_by(session_id=row.id,released_at=None).count()==0


def test_owner_approval_before_boundary_no_restart(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);w=e.db.session.get(e.m.CafeWallet,(1,1));w.balance=0
        model=sys.modules['app.models.session_extension']
        e.db.session.add(model.SessionExtensionPolicy(vendor_id=1,credit_mode='owner_approval'));e.db.session.commit()
        q,body=extend(e,row)
        assert q.status=='approval_pending' and not c.segments(row) and w.reserved==0
        c.decide(row,q,{'decision':'approve','revision':row.revision,'idempotency_key':'owner-approval-key'}, {'id':'owner','name':'Owner'})
        e.db.session.commit()
        assert q.status=='granted' and qr.state=='active' and len(c.segments(row))==1
        assert c.segments(row)[0].charged==0
        c.finish(row);e.db.session.commit()
        with pytest.raises(e.s.CafeError): c.decide(row,q,{'decision':'approve','revision':row.revision,'idempotency_key':'late-approval-key'},{'id':'owner','name':'Owner'})


def test_conflict_needs_staff_resolution(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);q,_=c.quote(row)
        from app.services.cafe_slot_reservations import local_window
        start,end=local_window(q.starts_at,q.ends_at)
        e.db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES (1,'upcoming',999,:day,:start,:end)"),{'day':start.date(),'start':start.time(),'end':end.time()});e.db.session.commit()
        c.continue_session(row,q.id,{'revision':row.revision,'idempotency_key':'conflict-request-key','credit_consent':True});e.db.session.commit()
        assert q.status=='conflict_pending' and not c.segments(row)
        e.db.session.execute(text("UPDATE vendor_1_dashboard SET book_status='cancelled' WHERE book_id=999"))
        c.decide(row,q,{'revision':row.revision,'decision':'retry','idempotency_key':'conflict-resolve-key'},{'id':'owner','name':'Owner'});e.db.session.commit()
        assert q.status=='granted'


def test_credit_proration_collection_replay_and_negative_net(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);w=e.db.session.get(e.m.CafeWallet,(1,1));w.balance=100;e.db.session.commit()
        q,_=extend(e,row);part=c.segments(row)[0]
        c.accrue(row,part.starts_at+(part.ends_at-part.starts_at)/2);e.db.session.commit()
        assert part.credit_due>0 and c.snapshot(row)['billing']['net_cafe_balance_paise']<0
        # Freeze at the same synthetic instant to check exactly one charge.
        row.stop_at=part.starts_at+(part.ends_at-part.starts_at)/2
        c.finish(row,row.stop_at);e.db.session.commit()
        due=c.snapshot(row)['billing']['amount_due_paise'];before=w.balance
        data={'amount_paise':due,'revision':row.revision,'method':'cash','idempotency_key':'extension-receipt-key'}
        c.receipt(row,data,{'id':'1','name':'Sam'});e.db.session.commit();c.receipt(row,data,{'id':'1','name':'Sam'});e.db.session.commit()
        assert c.snapshot(row)['billing']['amount_due_paise']==0 and w.balance==before
        assert e.m.CafeLedger.query.filter_by(kind='session_collection').count()==1


def test_credit_requires_consent_and_limit(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);w=e.db.session.get(e.m.CafeWallet,(1,1));w.balance=0;e.db.session.commit()
        q,_=c.quote(row);e.db.session.commit()
        with pytest.raises(e.s.CafeError): c.continue_session(row,q.id,{'revision':row.revision,'idempotency_key':'no-consent-key','credit_consent':False})
        e.db.session.rollback()
        model=sys.modules['app.models.session_extension'];e.db.session.add(model.SessionExtensionPolicy(vendor_id=1,credit_mode='automatic',credit_limit=0));e.db.session.commit()
        q,_=c.quote(row);e.db.session.commit()
        with pytest.raises(e.s.CafeError): c.continue_session(row,q.id,{'revision':row.revision,'idempotency_key':'limit-request-key','credit_consent':True})


def test_device_scope_staff_policy_and_stop_idempotency(env):
    e=env
    with e.app.app_context():
        row,qr=active(e);client=e.app.test_client()
        bad=client.post('/api/kiosk/session/stop',headers=auth('agent-other'),json={'runtime_id':row.id,'revision':row.revision,'mode':'now','idempotency_key':'scope-stop-key'})
        assert bad.status_code==404
        data={'runtime_id':row.id,'revision':row.revision,'mode':'now','idempotency_key':'valid-stop-key'}
        result=client.post('/api/kiosk/session/stop',headers=auth('agent-secret'),json=data)
        assert result.status_code==200 and result.json['billing']['is_final']
        assert client.post('/api/kiosk/session/stop',headers=auth('agent-secret'),json=data).status_code==200
        policy=client.put('/api/cafe/1/extension-policy',headers=auth(staff_token(e)),json={'self_qr_credit_mode':'automatic','credit_limit_paise':None})
        assert policy.status_code==403


def test_migration_repeatable_guard_and_outbox(env):
    e=env
    with e.app.app_context():
        from pathlib import Path
        script=(Path(__file__).parents[1]/'sql/20261007_kiosk_extensions.sql').read_text()
        conn=e.db.engine.raw_connection()
        try:
            conn.cursor().execute(script);conn.commit();conn.cursor().execute(script);conn.commit()
        finally: conn.close()
        row,qr=active(e);q,_=extend(e,row)
        c=engine();c.dispatch()
        model=sys.modules['app.models.session_extension']
        assert model.SessionOutbox.query.filter_by(published_at=None).count()==0
        count=model.SessionNotice.query.count();c.notice(row,'extension_granted');e.db.session.commit()
        assert model.SessionNotice.query.count()==count
        from app.services.cafe_slot_reservations import local_window
        start,end=local_window(q.starts_at,q.ends_at)
        # Physical assignment cannot sell a protected interval even if another
        # client bypasses the HTTP continuation endpoints.
        e.db.session.execute(text('INSERT INTO bookings(id,user_id,game_id,status) VALUES (999,2,100,\'confirmed\')'))
        with pytest.raises(Exception):
            e.db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES (1,'upcoming',999,:day,:start,:end)"),{'day':start.date(),'start':start.time(),'end':end.time()})
        e.db.session.rollback()


def test_topup_repays_debt_before_spendable_balance(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);w=e.db.session.get(e.m.CafeWallet,(1,1));w.balance=0;e.db.session.commit()
        q,_=extend(e,row);part=c.segments(row)[0]
        cutoff=part.starts_at+(part.ends_at-part.starts_at)/2
        c.finish(row,cutoff);e.db.session.commit()
        due=c.debt(1,1);assert due>0
        body={'amount':due+100,'method':'cash','idempotency_key':'repay-topup-key'}
        e.s.topup(1,1,body,{'id':'1','name':'Sam'});e.db.session.commit()
        e.s.topup(1,1,body,{'id':'1','name':'Sam'});e.db.session.commit()
        assert w.balance==100 and c.debt(1,1)==0
        assert e.m.CafeLedger.query.filter_by(kind='credit_repayment').count()==1


def test_normal_booking_extends_same_session_and_releases_once(env, monkeypatch):
    e=env
    with e.app.app_context():
        import types
        from app.services.cafe_slot_reservations import local_window
        from sqlalchemy import Table
        # Reflect the fixture's real booking table to exercise normal booking ORM mutations.
        booking_table=Table('bookings',e.db.metadata,autoload_with=e.db.engine)
        class Booking(e.db.Model): __table__=booking_table
        mod=types.ModuleType('app.models.booking');mod.Booking=Booking;monkeypatch.setitem(sys.modules,mod.__name__,mod)
        for name,kind in [('user_id','integer'),('game_id','integer'),('username','varchar')]:
            e.db.session.execute(text(f'ALTER TABLE vendor_1_dashboard ADD COLUMN {name} {kind}'))
        now=datetime.utcnow();local,_=local_window(now,now)
        start=local.replace(minute=30*(local.minute//30),second=0,microsecond=0);end=start+timedelta(minutes=30)
        base_slot=100+start.hour*2+start.minute//30
        e.db.session.execute(text("INSERT INTO bookings(id,user_id,game_id,slot_id,status,squad_details) VALUES(999,1,100,:slot,'checked_in',CAST(:details AS json))"),{'slot':base_slot,'details':'{"assigned_console_ids":[1],"slot_units":1}'} )
        e.db.session.execute(text("INSERT INTO vendor_1_dashboard(console_id,book_status,book_id,date,start_time,end_time,user_id,game_id,username) VALUES(1,'current',999,:day,:start,:end,1,100,'Test')"),{'day':start.date(),'start':start.time(),'end':end.time()})
        e.db.session.commit()
        from app.services.slot_capacity import reserve_slot
        reserve_slot(e.db.session,1,base_slot,start.date());e.db.session.commit()
        c=engine();row=c.attach(e.db.session.get(e.Link,1),{'kind':'booking','id':'999'});e.db.session.commit()
        q,body=extend(e,row,consent=False)
        assert q.status=='granted' and row.source_id=='999'
        assert c.segments(row)[0].funding==0
        c.finish(row,q.starts_at+(q.ends_at-q.starts_at)/2);e.db.session.commit()
        due=c.snapshot(row)['billing']['amount_due_paise'];assert due>0
        assert e.db.session.get(Booking,999).status=='completed'
        assert e.db.session.get(Booking,999).squad_details['remaining_slot_units']==0
        base_available=e.db.session.execute(text('SELECT available_slot FROM vendor_1_slot WHERE slot_id=:slot AND date=:day'),{'slot':base_slot,'day':start.date()}).scalar()
        assert base_available==2
        count=e.m.CafeSlotReservation.query.filter_by(session_id=row.id,released_at=None).count();assert count==0
        c.finish(row);e.db.session.commit();assert c.snapshot(row)['billing']['amount_due_paise']==due


def test_capacity_exhaustion_cannot_be_overridden_by_owner(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);q,_=c.quote(row)
        from app.services.cafe_slot_reservations import scheduled_slots,local_window
        from types import SimpleNamespace
        start,end=local_window(q.starts_at,q.ends_at)
        source_claims={(r.date,r.slot_id) for r in e.m.CafeSlotReservation.query.filter_by(session_id=qr.id,released_at=None).all()}
        rows=scheduled_slots(SimpleNamespace(vendor_id=1,console_id=1),start,end)
        # Make unheld next capacity unavailable, simulating a competing app booking.
        unheld=[r for r in rows if (r['date'],r['slot_id']) not in source_claims]
        if not unheld:
            q.starts_at=row.reserved_until=qr.ends_at+timedelta(hours=2);q.ends_at=q.starts_at+timedelta(minutes=30)
            start,end=local_window(q.starts_at,q.ends_at);rows=scheduled_slots(SimpleNamespace(vendor_id=1,console_id=1),start,end);unheld=rows
        for r in unheld:e.db.session.execute(text('UPDATE vendor_1_slot SET available_slot=0,is_available=false WHERE date=:day AND slot_id=:id'),{'day':r['date'],'id':r['slot_id']})
        q.amount=c.quoted_amount(row,q);q.revision=row.revision;e.db.session.commit()
        c.continue_session(row,q.id,{'revision':row.revision,'idempotency_key':'exhausted-slot-key','credit_consent':True});e.db.session.commit()
        assert q.status=='conflict_pending' and not c.segments(row)


def test_billing_ticks_do_not_invalidate_quote_revision_and_stop_is_not_blocked(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);q,body=extend(e,row)
        revision=row.revision;seq=row.event_sequence
        c.changed(row,state_changed=False);e.db.session.commit()
        assert row.revision==revision and row.event_sequence>seq
        c.stop(row,{'mode':'now','revision':1,'idempotency_key':'urgent-stop-key'});e.db.session.commit()
        assert row.ended_at is not None


def test_credit_ledger_and_waiver_are_audited_and_not_cash(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);w=e.db.session.get(e.m.CafeWallet,(1,1));w.balance=0;e.db.session.commit()
        q,_=extend(e,row);part=c.segments(row)[0];c.finish(row,part.ends_at);e.db.session.commit()
        model=sys.modules['app.models.session_extension'];due=c.snapshot(row)['billing']['amount_due_paise']
        assert sum(entry.amount for entry in model.SessionCreditEntry.query.all())==due
        c.receipt(row,{'amount_paise':due,'revision':row.revision,'method':'waiver','reason':'Owner approved goodwill','idempotency_key':'waive-extension-key'}, {'id':'1','name':'Sam'})
        e.db.session.commit();result=c.snapshot(row)
        assert result['billing']['collected_paise']==0 and result['billing']['waived_paise']==due
        assert result['billing']['amount_due_paise']==0
        assert sum(entry.amount for entry in model.SessionCreditEntry.query.all())==0
        entry=model.SessionCreditEntry.query.first();entry.amount=999
        with pytest.raises(ValueError):e.db.session.flush()
        e.db.session.rollback()


def test_outbox_failure_is_retryable_and_staff_event_has_no_wallet(env,monkeypatch):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);model=sys.modules['app.models.session_extension']
        socket=sys.modules['app.services.websocket_service'].socketio
        socket.emit.side_effect=RuntimeError('transient transport')
        c.dispatch();assert model.SessionOutbox.query.filter_by(published_at=None).count()>0
        socket.emit.side_effect=None;socket.emit.reset_mock();c.dispatch()
        assert model.SessionOutbox.query.filter_by(published_at=None).count()==0
        staff=[call for call in socket.emit.call_args_list if call.kwargs.get('room')=='vendor_1' and call.args[0]=='session.updated']
        assert staff and 'snapshot' not in staff[0].args[1]


def test_changed_quote_price_is_not_silently_charged(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);q,_=c.quote(row);e.db.session.commit()
        e.db.session.execute(text('UPDATE available_games SET single_slot_price=99 WHERE id=100'));e.db.session.commit()
        with pytest.raises(e.s.CafeError):c.continue_session(row,q.id,{'revision':row.revision,'idempotency_key':'changed-price-key','credit_consent':True})
        e.db.session.rollback();assert not c.segments(row)


def test_concurrent_stop_captures_once(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);q,_=extend(e,row);rid=row.id;cutoff=q.starts_at+(q.ends_at-q.starts_at)/2
        e.db.session.remove()
    from concurrent.futures import ThreadPoolExecutor
    def stop():
        with e.app.app_context():
            c=engine();row=c.lock_row(rid);c.finish(row,cutoff);e.db.session.commit()
            result=c.snapshot(row);e.db.session.remove();return result
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:stop(),range(2)))
    assert results[0]['billing']==results[1]['billing'] or results[0]['billing']['total_paise']==results[1]['billing']['total_paise']
    with e.app.app_context():
        assert e.m.CafeLedger.query.filter_by(kind='extension_capture').count()==1
        assert e.m.CafeWallet.query.get((1,1)).reserved==0


def test_migration_creates_complete_schema_from_scratch(env):
    e=env
    with e.app.app_context():
        from pathlib import Path
        from sqlalchemy import inspect
        model=sys.modules['app.models.session_extension']
        names=[v.__tablename__ for v in vars(model).values() if isinstance(v,type) and hasattr(v,'__tablename__')]
        for name in names:e.db.session.execute(text(f'DROP TABLE IF EXISTS {name} CASCADE'))
        e.db.session.commit()
        conn=e.db.engine.raw_connection()
        try:conn.cursor().execute((Path(__file__).parents[1]/'sql/20261007_kiosk_extensions.sql').read_text());conn.commit()
        finally:conn.close()
        columns={c['name'] for c in inspect(e.db.engine).get_columns('kiosk_runtime_sessions')}
        assert {'event_sequence','console_claim','revision','credit_mode'}<=columns
        row,qr=active(e);q,_=extend(e,row)
        assert q.status=='granted'


def test_gamer_stream_scope_and_expiry(env):
    e=env
    with e.app.app_context():
        from flask_socketio import SocketIO
        from test_cafe_wallet import gamer
        rt=sys.modules['app.services.session_realtime'];socket=SocketIO(e.app,async_mode='threading')
        rt.register_gamer_realtime(e.app,socket)
        bad=socket.test_client(e.app,namespace='/cafe-gamer',auth={'token':'invalid'})
        assert not bad.is_connected('/cafe-gamer')
        client=socket.test_client(e.app,namespace='/cafe-gamer',auth={'token':gamer(e),'user_id':2})
        assert client.is_connected('/cafe-gamer')
        socket.emit('session.updated',{'private':True},room='cafe-user:2',namespace='/cafe-gamer')
        assert not client.get_received('/cafe-gamer')
        socket.emit('session.updated',{'private':True},room='cafe-user:1',namespace='/cafe-gamer')
        assert client.get_received('/cafe-gamer')
        for sid in rt._gamer_sids:rt._gamer_sids[sid]=0
        rt.expire_gamer_connections();assert not client.is_connected('/cafe-gamer')


def test_offline_kiosk_cannot_receive_new_credit_or_time(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);q,_=c.quote(row);row.last_seen_at=datetime.utcnow()-timedelta(minutes=2);e.db.session.commit()
        with pytest.raises(e.s.CafeError):c.grant(row,q)
        e.db.session.rollback();assert not c.segments(row)
        # A device-authenticated poll restores presence without authorizing credit.
        result=e.app.test_client().get('/api/kiosk/session',headers=auth('agent-secret'))
        assert result.status_code==200
        assert row.last_seen_at>datetime.utcnow()-timedelta(seconds=10)
        assert not c.segments(row)


def test_partial_wallet_funding_does_not_wait_for_owner(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);w=e.db.session.get(e.m.CafeWallet,(1,1));w.balance=100
        model=sys.modules['app.models.session_extension']
        e.db.session.add(model.SessionExtensionPolicy(vendor_id=1,credit_mode='owner_approval'));e.db.session.commit()
        original=row.reserved_until;q,_=extend(e,row)
        assert q.status=='approval_pending'
        part=c.segments(row)[0]
        assert part.funding==part.amount<=100
        assert original<row.reserved_until<q.ends_at and q.starts_at==row.reserved_until
        c.decide(row,q,{'decision':'approve','revision':row.revision,'idempotency_key':'partial-owner-approval'},{'id':'owner','name':'Owner'})
        e.db.session.commit()
        assert row.reserved_until==q.ends_at and len(c.segments(row))==2


def test_new_wallet_funds_pay_future_usage_without_rewriting_credit(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);w=e.db.session.get(e.m.CafeWallet,(1,1));w.balance=0;e.db.session.commit()
        q,_=extend(e,row);part=c.segments(row)[0];duration=part.ends_at-part.starts_at
        c.accrue(row,part.starts_at+duration/4);e.db.session.commit();past_credit=part.credit_due
        assert past_credit>0
        w.balance=10000;e.db.session.commit()
        c.accrue(row,part.starts_at+duration/2);e.db.session.commit()
        assert part.credit_due==past_credit and part.captured>0
        c.finish(row,part.starts_at+duration/2);e.db.session.commit()
        assert w.reserved==0 and part.credit_due==past_credit


def test_extension_revenue_counts_accrual_not_collection(env):
    e=env
    with e.app.app_context():
        c=engine();row,qr=active(e);w=e.db.session.get(e.m.CafeWallet,(1,1));w.balance=0;e.db.session.commit()
        q,_=extend(e,row);part=c.segments(row)[0]
        c.finish(row,part.starts_at+(part.ends_at-part.starts_at)/2);e.db.session.commit()
        day=c.local_window(datetime.utcnow(),datetime.utcnow())[0].date()
        before=c.financial_totals(1,day);assert before['earned_paise']==part.charged and before['pending_paise']==part.credit_due
        c.receipt(row,{'amount_paise':part.credit_due,'method':'waiver','reason':'Test approved waiver','revision':row.revision,'idempotency_key':'summary-waiver-key'},{'id':'owner','name':'Owner'});e.db.session.commit()
        after=c.financial_totals(1,day);assert after['earned_paise']==0 and after['pending_paise']==0


def test_squad_base_capacity_release_is_once_per_device(env):
    e=env
    with e.app.app_context():
        from types import SimpleNamespace
        from app.services.slot_capacity import reserve_slot
        c=engine();row,qr=active(e)
        local,_=c.local_window(datetime.utcnow()+timedelta(hours=2),datetime.utcnow()+timedelta(hours=2));slot=100+local.hour*2+local.minute//30
        e.db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES(99,'completed',998,:day,:start,:end)"),{'day':local.date(),'start':local.time(),'end':(local+timedelta(minutes=10)).time()})
        reserve_slot(e.db.session,1,slot,local.date(),2);e.db.session.commit()
        booking=SimpleNamespace(id=998,slot_id=slot);details={'slot_units':2,'assigned_console_ids':[1,2]}
        c.release_base_booking(row,booking,details,{1,2},{1});e.db.session.commit()
        assert details['remaining_slot_units']==1
        c.release_base_booking(row,booking,details,{1,2},{1});e.db.session.commit();assert details['remaining_slot_units']==1
        sibling=SimpleNamespace(id=row.id,vendor_id=1,console_id=2)
        c.release_base_booking(sibling,booking,details,{1,2},{1,2});e.db.session.commit()
        assert details['remaining_slot_units']==0
        assert e.db.session.execute(text('SELECT available_slot FROM vendor_1_slot WHERE slot_id=:slot AND date=:day'),{'slot':slot,'day':local.date()}).scalar()==2


def test_public_availability_stream_cannot_select_private_rooms(env):
    e=env
    with e.app.app_context():
        from flask_socketio import SocketIO
        realtime=sys.modules['app.services.session_realtime'];socket=SocketIO(e.app)
        realtime.register_gamer_realtime(e.app,socket)
        client=socket.test_client(e.app,namespace='/cafe-availability')
        assert client.emit('watch',{'vendor_id':1,'room':'vendor_1'},namespace='/cafe-availability',callback=True)=={'ok':True}
        assert client.emit('watch',{'vendor_id':999},namespace='/cafe-availability',callback=True)=={'ok':False}
        socket.emit('session.updated',{'private':True},room='vendor_1')
        assert not client.get_received('/cafe-availability')
        client.disconnect(namespace='/cafe-availability')
