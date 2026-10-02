from datetime import datetime, timedelta
import sys
from unittest.mock import Mock
import pytest
from sqlalchemy import text
from test_cafe_wallet import env, fund, gamer, auth, staff_token


def services():
    return sys.modules['app.services.cafe_continuation_service']


def started(e):
    fund(e)
    row=e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'paid-session-key')
    e.db.session.commit()
    e.s.acknowledge(row.id,e.db.session.get(e.Link,1),row.command_token,True)
    # Set expiry exactly now, without waiting an hour.
    row.ends_at=datetime.utcnow()-timedelta(seconds=1)
    e.db.session.commit()
    return row


def request_more(e,parent):
    c=services()
    client=e.app.test_client()
    quote=client.get(f'/api/cafe/sessions/{parent.id}/continuation/quote',headers=auth(gamer(e)))
    assert quote.status_code==200
    amount=quote.json['durations'][0]['amount']
    assert amount is not None
    return c.request_continuation(parent.id,1,{'minutes':60,'expected_amount':amount,'idempotency_key':'continue-request-key'})


def approve(e,parent):
    request=request_more(e,parent);e.db.session.commit()
    row=services().decide(1,request.id,{'decision':'approve','expected_amount':request.amount},{'id':'owner-1','name':'Owner'})
    e.db.session.commit()
    return e.db.session.get(e.m.CafePlaySession,row.session_id)


def test_credit_due_only_after_ack_and_collection_does_not_change_wallet(env):
    e=env
    with e.app.app_context():
        parent=started(e);child=approve(e,parent)
        w=e.db.session.get(e.m.CafeWallet,(1,1));balance=w.balance
        assert child.kind=='owner_credit' and child.due_amount==0 and w.reserved==0
        assert parent.state=='completed' and parent.console_claim is None
        e.s.acknowledge(child.id,e.db.session.get(e.Link,1),child.command_token,True);e.db.session.commit()
        assert child.due_amount==child.amount and w.balance==balance
        assert services().snapshot(child)['play_allowed'] is True
        services().end_session(child.id,{'id':'1','name':'Sam'});e.db.session.commit()
        body={'expected_amount':child.amount,'method':'cash','idempotency_key':'credit-pay-key'}
        services().settle(1,child.id,body,{'id':'1','name':'Sam'});e.db.session.commit()
        services().settle(1,child.id,body,{'id':'1','name':'Sam'});e.db.session.commit()
        assert e.m.CafeLedger.query.filter_by(kind='session_collection').count()==1
        assert services().snapshot(child)['payment_due']==0 and w.balance==balance
        assert e.m.CafeSlotReservation.query.filter_by(session_id=child.id,released_at=None).count()==0


def test_failed_credit_start_no_debt_or_stuck_capacity(env):
    e=env
    with e.app.app_context():
        child=approve(e,started(e))
        e.s.acknowledge(child.id,e.db.session.get(e.Link,1),child.command_token,False);e.db.session.commit()
        assert child.state=='failed' and child.due_amount==0 and child.console_claim is None
        assert e.m.CafeSlotReservation.query.filter_by(session_id=child.id,released_at=None).count()==0


def test_request_and_email_are_idempotent_reject_does_not_hold_slot(env):
    e=env
    with e.app.app_context():
        parent=started(e);r=request_more(e,parent);e.db.session.commit()
        assert request_more(e,parent).id==r.id
        assert e.m.CafeOwnerEmail.query.count()==1
        services().decide(1,r.id,{'decision':'reject'},{'id':'owner','name':'Owner'});e.db.session.commit()
        e.s.expire_sessions()
        assert r.state=='rejected' and r.pending_key is None
        assert e.m.CafePlaySession.query.count()==1
        assert parent.console_claim is None


def test_low_time_warning_once_expiry_stop_and_reconnect(env):
    e=env
    with e.app.app_context():
        parent=started(e);parent.ends_at=datetime.utcnow()+timedelta(minutes=3);e.db.session.commit()
        e.s.expire_sessions();e.s.expire_sessions()
        emits=sys.modules['app.services.websocket_service'].socketio.emit
        assert sum(call.args[0]=='session.warning' for call in emits.call_args_list)==1
        parent.ends_at=datetime.utcnow()-timedelta(seconds=1);e.db.session.commit();e.s.expire_sessions()
        assert parent.state=='completed'
        assert any(call.args[0]=='session.stop' for call in emits.call_args_list)
        response=e.app.test_client().get('/api/cafe/agent/status',headers=auth('agent-secret'))
        assert response.status_code==200 and response.json['play_allowed'] is False
        assert response.json['session']['warning']=='time_exhausted'


def test_owner_only_cross_vendor_and_gamer_ownership(env):
    e=env
    with e.app.app_context():
        parent=started(e);r=request_more(e,parent);e.db.session.commit()
        client=e.app.test_client()
        assert client.post(f'/api/cafe/1/continuations/{r.id}/decision',json={'decision':'reject'},headers=auth(staff_token(e))).status_code==403
        assert client.post(f'/api/cafe/2/continuations/{r.id}/decision',json={'decision':'reject'},headers=auth(staff_token(e,role='owner',vid=2))).status_code==404
        assert client.get(f'/api/cafe/sessions/{parent.id}/continuation/quote',headers=auth(gamer(e,2))).status_code==404
        assert client.post('/api/cafe/agent/continuation',headers=auth('agent-other'),json={'session_id':parent.id,'command_token':parent.command_token}).status_code==403
        response=client.get('/api/cafe/1/sessions/live',headers=auth(staff_token(e,role='owner')))
        assert response.status_code==200 and response.json['requests'][0]['id']==r.id
        assert client.post(f'/api/cafe/1/continuations/{r.id}/decision',json={'decision':'reject'},headers=auth(staff_token(e,role='owner'))).status_code==200


def test_approval_never_starts_before_paid_expiry(env):
    e=env
    with e.app.app_context():
        parent=started(e);parent.ends_at=datetime.utcnow()+timedelta(minutes=2);e.db.session.commit()
        r=request_more(e,parent);e.db.session.commit()
        with pytest.raises(e.s.CafeError,match='still running'):
            services().decide(1,r.id,{'decision':'approve','expected_amount':r.amount},{'id':'owner','name':'Owner'})
        e.db.session.rollback()
        assert e.m.CafePlaySession.query.count()==1


def test_owner_email_retry_outbox_does_not_duplicate_request(env,monkeypatch):
    e=env
    with e.app.app_context():
        r=request_more(e,started(e));e.db.session.commit()
        mail=sys.modules['app.services.cafe_owner_email']
        sender=Mock(side_effect=[TimeoutError(),None]);monkeypatch.setattr(mail,'send_owner_email',sender)
        mail.dispatch_owner_emails()
        out=e.db.session.get(e.m.CafeOwnerEmail,r.id)
        assert out.attempts==1 and out.sent_at is None
        out.next_attempt_at=datetime.utcnow()-timedelta(seconds=1);e.db.session.commit()
        mail.dispatch_owner_emails();mail.dispatch_owner_emails()
        assert sender.call_count==2 and out.sent_at is not None
        assert e.m.CafeContinuation.query.count()==1


def test_request_expires_without_claiming_pc(env):
    e=env
    with e.app.app_context():
        parent=started(e);r=request_more(e,parent);e.db.session.commit()
        r.expires_at=datetime.utcnow()-timedelta(seconds=1);e.db.session.commit()
        e.s.expire_sessions()
        assert r.state=='expired' and r.pending_key is None
        assert parent.console_claim is None


def test_unpaid_credit_cannot_be_bypassed_via_original_session_or_checkout(env):
    e=env
    with e.app.app_context():
        parent=started(e);child=approve(e,parent)
        e.s.acknowledge(child.id,e.db.session.get(e.Link,1),child.command_token,True);e.db.session.commit()
        services().end_session(child.id,{'id':'owner','name':'Owner'});e.db.session.commit()
        with pytest.raises(e.s.CafeError,match='outstanding'):
            e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'another-checkout-key')
        e.db.session.rollback()
        with pytest.raises(e.s.CafeError,match='previous approved'):
            services().request_continuation(parent.id,1,{'minutes':60,'expected_amount':10000,'idempotency_key':'another-request-key'})
        e.db.session.rollback()


def test_future_booking_blocks_approval_and_keeps_existing_reservation_consistent(env):
    e=env
    if not e.pg: pytest.skip('PostgreSQL assignment guards')
    with e.app.app_context():
        parent=started(e);r=request_more(e,parent);e.db.session.commit()
        # Requests claim no inventory; expiry releases the original paid hold.
        e.s.expire_sessions()
        from app.services.cafe_slot_reservations import local_window
        start,end=local_window(datetime.utcnow()+timedelta(minutes=2),datetime.utcnow()+timedelta(minutes=20))
        e.db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES (1,'upcoming',333,:day,:start,:end)"),
            {'day':start.date(),'start':start.time(),'end':end.time()});e.db.session.commit()
        before=e.db.session.execute(text('SELECT sum(available_slot) FROM vendor_1_slot')).scalar()
        with pytest.raises(e.s.CafeError,match='another booking'):
            services().decide(1,r.id,{'decision':'approve','expected_amount':r.amount},{'id':'owner','name':'Owner'})
        e.db.session.rollback()
        assert r.state=='pending' and parent.console_claim is None
        assert before==e.db.session.execute(text('SELECT sum(available_slot) FROM vendor_1_slot')).scalar()


def test_competing_owner_approvals_create_one_credit_session(env):
    e=env
    if not e.pg: pytest.skip('Requires independent PostgreSQL transactions')
    with e.app.app_context():
        parent=started(e);r=request_more(e,parent);e.db.session.commit();request_id=r.id;amount=r.amount
    from concurrent.futures import ThreadPoolExecutor
    import threading
    barrier=threading.Barrier(2)
    def decide_once():
        with e.app.app_context():
            barrier.wait()
            row=services().decide(1,request_id,{'decision':'approve','expected_amount':amount},{'id':'owner','name':'Owner'})
            e.db.session.commit();return row.session_id
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:decide_once(),range(2)))
    with e.app.app_context():
        assert results[0]==results[1]
        assert e.m.CafePlaySession.query.filter_by(kind='owner_credit').count()==1


def test_collection_requires_completed_play_and_expected_amount(env):
    e=env
    with e.app.app_context():
        child=approve(e,started(e));e.s.acknowledge(child.id,e.db.session.get(e.Link,1),child.command_token,True);e.db.session.commit()
        with pytest.raises(e.s.CafeError,match='completed unpaid'):
            services().settle(1,child.id,{'expected_amount':child.amount,'method':'cash','idempotency_key':'invalid-pay-key'},{'id':'1','name':'Sam'})
        e.db.session.rollback();services().end_session(child.id,{'id':'1','name':'Sam'});e.db.session.commit()
        with pytest.raises(e.s.CafeError,match='Balance due changed'):
            services().settle(1,child.id,{'expected_amount':0,'method':'cash','idempotency_key':'invalid-pay-key'},{'id':'1','name':'Sam'})
        e.db.session.rollback()
        assert e.m.CafeLedger.query.filter_by(kind='session_collection').count()==0


def test_continuation_migration_is_repeatable_and_preserves_live_play(env):
    e=env
    if not e.pg: pytest.skip('PostgreSQL migration')
    from pathlib import Path
    with e.app.app_context():
        parent=started(e);before=e.db.session.get(e.m.CafeWallet,(1,1)).balance
        sql=(Path(__file__).resolve().parents[1]/'sql/20261002_cafe_continuations.sql').read_text()
        raw=e.db.engine.raw_connection()
        try:
            raw.cursor().execute(sql);raw.commit()
            raw.cursor().execute(sql);raw.commit()
        finally:raw.close()
        e.db.session.expire_all()
        assert e.db.session.get(e.m.CafePlaySession,parent.id).state=='active'
        assert e.db.session.get(e.m.CafeWallet,(1,1)).balance==before
        assert parent.due_amount==0


def test_rejected_request_snapshot_and_single_prepare_command(env):
    e=env
    with e.app.app_context():
        parent=started(e);r=request_more(e,parent);e.db.session.commit()
        services().decide(1,r.id,{'decision':'reject'},{'id':'owner','name':'Owner'});e.db.session.commit()
        snapshot=services().snapshot(parent)
        assert snapshot['last_continuation']['state']=='rejected' and snapshot['continuation_request'] is None
        # A checkout publishes one command, not a duplicate from both the route
        # and capacity invalidation helper.
        e.s.expire_sessions()
        token=gamer(e);qr=e.c.signer().dumps({'link_id':1})
        socket=sys.modules['app.services.websocket_service'].socketio;socket.reset_mock()
        response=e.app.test_client().post('/api/cafe/checkout',headers=auth(token),json={
            'qr':qr,'minutes':60,'expected_amount':10000,'payment_method':'cafe_wallet','idempotency_key':'next-paid-key'})
        assert response.status_code==202,response.json
        assert sum(call.args[0]=='session.prepare' for call in socket.emit.call_args_list)==1


def test_wallet_budget_can_buy_affordable_time_below_configured_duration(env):
    e=env
    with e.app.app_context():
        fund(e,amount=3750)
        client=e.app.test_client();token=gamer(e);qr=e.c.signer().dumps({'link_id':1})
        response=client.get('/api/cafe/checkout/affordable',query_string={'qr':qr},headers=auth(token))
        assert response.status_code==200
        duration=response.json['duration'];assert duration['minutes']==22 and 0<duration['amount']<=3750
        purchase=client.post('/api/cafe/checkout',headers=auth(token),json={
            'qr':qr,'minutes':duration['minutes'],'expected_amount':duration['amount'],
            'use_available_balance':True,'payment_method':'cafe_wallet','idempotency_key':'budget-session-key'})
        assert purchase.status_code==202,purchase.json
        row=e.db.session.get(e.m.CafePlaySession,purchase.json['id'])
        e.s.acknowledge(row.id,e.db.session.get(e.Link,1),row.command_token,True);e.db.session.commit()
        w=e.db.session.get(e.m.CafeWallet,(1,1))
        assert w.balance==3750-duration['amount'] and w.reserved==0


def test_budget_duration_cannot_exceed_cafe_limit_or_turn_missing_price_into_zero(env):
    e=env
    with e.app.app_context():
        fund(e)
        with pytest.raises(e.s.CafeError,match='session limit'):
            e.s.reserve(1,1,e.db.session.get(e.Link,1),61,'budget-invalid-key',expected_amount=0,use_available_balance=True)
        e.db.session.rollback()
        with pytest.raises(e.s.CafeError,match='Price changed'):
            e.s.reserve(1,1,e.db.session.get(e.Link,1),22,'budget-zero-key',expected_amount=0,use_available_balance=True)
        e.db.session.rollback()
        assert e.m.CafePlaySession.query.count()==0
