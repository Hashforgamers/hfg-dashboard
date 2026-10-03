"""Owner-approved fixed-duration credit, independent of nonnegative wallet balances.

Requests do not hold slots. Approval rechecks capacity after funded play ends;
only a successful PC acknowledgement creates the agreed fixed-duration debt.
"""
from datetime import datetime, timedelta
import uuid
from flask import current_app
from app.extension.extensions import db
from app.models.cafe_wallet import CafePlaySession, CafeContinuation, CafeOwnerEmail, CafeShift, CafeLedger
from app.models.console_link_session import ConsoleLinkSession
from app.services.cafe_wallet_service import CafeError, wallet, reserve, integer, key, fingerprint, serialize, audit, ledger, policy, release_console


def overtime_charge(session, now=None):
    """Prorate extra whole minutes at the agreed session price, rounded up to paise."""
    import math
    if not session.ends_at or not session.started_at or session.minutes<=0:
        return 0
    finish=session.ended_at or now or datetime.utcnow()
    seconds=max(0,(finish-session.ends_at).total_seconds())
    return math.ceil(session.amount * math.ceil(seconds/60) / session.minutes)


def snapshot(session):
    result = serialize(session)
    now = datetime.utcnow()
    result['remaining_seconds'] = max(0, int((session.ends_at-now).total_seconds())) if session.ends_at else 0
    result['play_allowed'] = bool(session.state == 'active')
    result['stop_at'] = None
    result['auto_lock_at_end'] = False
    result['overtime_seconds'] = max(0,int(((session.ended_at or now)-session.ends_at).total_seconds())) if session.ends_at else 0
    result['overtime_amount'] = overtime_charge(session,now)
    result['payment_due'] = ((session.amount if session.kind=='owner_credit' else 0)+overtime_charge(session,now) if session.state=='active' else session.due_amount) if session.settled_at is None else 0
    result['billing'] = 'duration_plus_overtime'
    result['server_time'] = now.isoformat()+'Z'
    result['warning'] = 'time_exhausted' if session.state == 'completed' else (
        'overtime' if result['play_allowed'] and result['overtime_seconds']>0 else 'time_low' if result['play_allowed'] and result['remaining_seconds'] <= 300 else None)
    latest = CafeContinuation.query.filter_by(parent_id=session.id).order_by(CafeContinuation.created_at.desc()).first()
    result['last_continuation'] = serialize(latest) if latest else None
    pending = latest if latest and latest.state=='pending' else None
    result['continuation_request'] = serialize(pending) if pending else None
    approved = CafeContinuation.query.filter_by(parent_id=session.id,state='approved').order_by(CafeContinuation.created_at.desc()).first()
    result['next_session_id'] = approved.session_id if approved else None
    return result


def publish_session(session, event=None):
    from app.services.websocket_service import socketio
    try:
        from app.routes import _invalidate_vendor_caches
        _invalidate_vendor_caches(session.vendor_id)
    except Exception:
        current_app.logger.debug('Console cache invalidation unavailable', exc_info=True)
    try:
        payload = snapshot(session)
        socketio.emit('cafe_session_updated', payload, room=f'vendor_{session.vendor_id}')
        kind = event or ('session.stop' if session.state in ('failed','completed') else 'session.updated')
        if session.state == 'reserved':
            socketio.emit('session.prepare', dict(payload, command_token=session.command_token),
                          to=f'cafe-agent:{session.link_id}', namespace='/cafe-agent')
        else:
            socketio.emit(kind, payload, to=f'cafe-agent:{session.link_id}', namespace='/cafe-agent')
    except Exception:
        current_app.logger.exception('Cafe session notification failed session=%s',session.id)


def request_continuation(session_id, user_id, body):
    initial = CafePlaySession.query.filter_by(id=session_id,user_id=user_id).first()
    if not initial:
        raise CafeError('Session not found',404)
    wallet(initial.vendor_id,user_id)
    session = CafePlaySession.query.filter_by(id=session_id).populate_existing().with_for_update().one()
    minutes = integer(body.get('minutes'),5,720)
    idem = key(body.get('idempotency_key'))
    fp = fingerprint([session_id,minutes])
    old = CafeContinuation.query.filter_by(vendor_id=session.vendor_id,user_id=user_id,idempotency_key=idem).first()
    if old:
        if old.fingerprint != fp: raise CafeError('Idempotency key already used',409)
        return old
    now = datetime.utcnow()
    if session.kind == 'existing_booking' or session.state not in ('active','completed'):
        raise CafeError('Continue a wallet session after it has started',409)
    if not session.ends_at or now > session.ends_at+timedelta(minutes=15):
        raise CafeError('Continuation window expired. Start a new checkout.',409)
    if CafeContinuation.query.filter_by(pending_key=session.id).first():
        raise CafeError('An owner decision is already pending',409)
    if CafePlaySession.query.filter_by(vendor_id=session.vendor_id,user_id=user_id).filter(
        CafePlaySession.due_amount>0,CafePlaySession.settled_at.is_(None)).first():
        raise CafeError('Settle the previous approved duration before requesting more time',409)
    from app.services.cafe_session_pricing import session_prices, console_durations
    link = db.session.get(ConsoleLinkSession,session.link_id)
    # Quote the requested extension at funded expiry. Own claims already cover
    # the tail of that slot; approval will release and reserve transactionally.
    from app.services.cafe_slot_reservations import local_window
    start = max(now,session.ends_at)
    local,_ = local_window(start,start)
    local=local.replace(second=0,microsecond=0)
    durations = console_durations(link, now=local)
    if minutes not in [d['minutes'] for d in durations]:
        raise CafeError('Choose a configured duration',409)
    quotes = session_prices(link,[{'minutes':minutes}],now=local,check_capacity=False)
    quote = quotes[0]
    if quote['amount'] is None: raise CafeError(quote['unavailable_reason'],409)
    expected = integer(body.get('expected_amount'),0)
    if expected != quote['amount']: raise CafeError('Price changed. Reload the continuation quote.',409)
    row = CafeContinuation(id=str(uuid.uuid4()),vendor_id=session.vendor_id,user_id=user_id,
        parent_id=session.id,pending_key=session.id,idempotency_key=idem,fingerprint=fp,
        minutes=minutes,amount=expected,state='pending',expires_at=max(now,session.ends_at)+timedelta(minutes=15))
    db.session.add(row)
    # Resolve the account owner, rather than the gamer's email or an employee.
    from app.models.vendor import Vendor
    vendor = db.session.get(Vendor,session.vendor_id)
    account = getattr(vendor,'account',None)
    contact = getattr(vendor,'contact_info',None)
    recipient = getattr(account,'email',None) or getattr(contact,'email',None)
    db.session.add(CafeOwnerEmail(request_id=row.id,recipient=recipient,
                                  last_error=None if recipient else 'Owner email is missing'))
    audit(session.vendor_id,{'id':f'gamer-{user_id}','name':'Gamer self-service'},
        'continuation.requested',{'request_id':row.id,'session_id':session.id,'minutes':minutes,'amount':expected})
    return row


def decide(vendor_id, request_id, body, actor):
    initial = CafeContinuation.query.filter_by(id=request_id,vendor_id=vendor_id).first()
    if not initial: raise CafeError('Request not found',404)
    wallet(vendor_id,initial.user_id)
    row = CafeContinuation.query.filter_by(id=request_id).populate_existing().with_for_update().one()
    choice = body.get('decision')
    if choice not in ('approve','reject'): raise CafeError('Choose approve or reject')
    if row.state != 'pending':
        if (choice == 'approve' and row.state == 'approved') or (choice == 'reject' and row.state == 'rejected'): return row
        raise CafeError('Request already decided or expired',409)
    now = datetime.utcnow()
    if now >= row.expires_at: raise CafeError('Request expired',409)
    parent = CafePlaySession.query.filter_by(id=row.parent_id).populate_existing().with_for_update().one()
    if choice == 'approve':
        if CafePlaySession.query.filter_by(vendor_id=vendor_id,user_id=row.user_id).filter(
            CafePlaySession.due_amount>0,CafePlaySession.settled_at.is_(None)).first():
            raise CafeError('Settle the outstanding approved duration before more credit play',409)
        if parent.ends_at and now < parent.ends_at:
            raise CafeError('Funded play is still running. Approve after its timer ends.',409)
        if parent.state == 'active':
            parent.ended_at=now
            parent.due_amount=(parent.amount if parent.kind=='owner_credit' else 0)+overtime_charge(parent,now)
            parent.state='completed'
            release_console(parent)
        if parent.state != 'completed': raise CafeError('Source session is unavailable',409)
        amount = integer(body.get('expected_amount'),0)
        if amount != row.amount: raise CafeError('Review the requested price before approval',409)
        link = db.session.get(ConsoleLinkSession,parent.link_id)
        child = reserve(vendor_id,row.user_id,link,row.minutes,'credit:'+row.id,
                        expected_amount=amount,owner_credit=True)
        row.session_id = child.id
    row.state = 'approved' if choice == 'approve' else 'rejected'
    row.pending_key=None;row.decided_at=now;row.decided_by=actor['id']
    audit(vendor_id,actor,'continuation.'+row.state,{'request_id':row.id,'amount':row.amount,'minutes':row.minutes})
    return row


def end_session(session_id, actor):
    initial = db.session.get(CafePlaySession,session_id)
    if not initial: raise CafeError('Session not found',404)
    wallet(initial.vendor_id,initial.user_id)
    session = CafePlaySession.query.filter_by(id=session_id).populate_existing().with_for_update().one()
    if session.kind == 'existing_booking': raise CafeError('End this booking using the booking controls',409)
    if session.state == 'reserved':
        from app.services.cafe_wallet_service import acknowledge
        return acknowledge(session.id,db.session.get(ConsoleLinkSession,session.link_id),session.command_token,False)
    if session.state == 'active':
        session.ended_at=datetime.utcnow()
        session.due_amount=(session.amount if session.kind=='owner_credit' else 0)+overtime_charge(session)
        session.state='completed'
        release_console(session)
        audit(session.vendor_id,actor,'session.ended',{'session_id':session.id,'due_amount':session.due_amount})
    return session


def settle(vendor_id,session_id,body,actor):
    initial = CafePlaySession.query.filter_by(id=session_id,vendor_id=vendor_id).first()
    if not initial: raise CafeError('Session not found',404)
    w = wallet(vendor_id,initial.user_id)
    row = CafePlaySession.query.filter_by(id=session_id).populate_existing().with_for_update().one()
    idem=key(body.get('idempotency_key'));method=body.get('method')
    amount=integer(body.get('expected_amount'),0);fp=fingerprint([session_id,amount,method])
    old=CafeLedger.query.filter_by(vendor_id=vendor_id,idempotency_key=idem).first()
    if old:
        if old.fingerprint!=fp or old.actor_id!=actor['id']: raise CafeError('Idempotency key already used',409)
        return row
    if row.state!='completed' or row.kind not in ('owner_credit','wallet') or row.settled_at or not row.due_amount:
        raise CafeError('There is no completed unpaid duration to settle',409)
    if amount!=row.due_amount: raise CafeError('Balance due changed. Refresh.',409)
    if method not in policy(vendor_id)['desk_methods']: raise CafeError('Desk payment method disabled',403)
    shift=CafeShift.query.filter_by(open_key=f"{vendor_id}:{actor['id']}").first()
    if not shift: raise CafeError('Open your shift before collecting payment',409)
    ledger(w,'session_collection',amount,actor,idem,fp,session_id=row.id,method=method,
           shift_id=shift.id,reason='Gaming duration and overtime collected at desk')
    row.settled_at=datetime.utcnow()
    audit(vendor_id,actor,'session.settled',{'session_id':row.id,'amount':amount,'method':method})
    return row


def reconcile_notifications(now):
    warnings=[]
    candidates=CafePlaySession.query.filter(CafePlaySession.state=='active',
        CafePlaySession.ends_at>now,CafePlaySession.ends_at<=now+timedelta(minutes=5),
        CafePlaySession.warning_sent_at.is_(None)).order_by(CafePlaySession.vendor_id,CafePlaySession.id).all()
    for initial in candidates:
        wallet(initial.vendor_id,initial.user_id)
        row=CafePlaySession.query.filter_by(id=initial.id).populate_existing().with_for_update().one()
        if row.state=='active' and row.warning_sent_at is None:
            row.warning_sent_at=now;warnings.append(row)
    for initial in CafeContinuation.query.filter(CafeContinuation.state=='pending',CafeContinuation.expires_at<=now).order_by(CafeContinuation.vendor_id,CafeContinuation.id).all():
        wallet(initial.vendor_id,initial.user_id)
        row=CafeContinuation.query.filter_by(id=initial.id).populate_existing().with_for_update().one()
        if row.state!='pending' or row.expires_at>now: continue
        row.state='expired';row.pending_key=None
        parent=db.session.get(CafePlaySession,row.parent_id)
        if parent: warnings.append(parent)
    return warnings
