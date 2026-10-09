"""Unified, transaction-owned extension engine for desk/app and Self QR play."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid
import math
from sqlalchemy import text, inspect
from flask import current_app
from app.extension.extensions import db
from app.models.session_extension import (SessionExtensionPolicy, RuntimeSession, ExtensionSegment,
    ExtensionQuote, SessionNotice, SessionOutbox, SessionReceipt, SessionCreditEntry)
from app.models.cafe_wallet import CafePlaySession, CafeSlotReservation, CafeShift
from app.models.console import Console
from app.models.console_link_session import ConsoleLinkSession
from app.services.cafe_wallet_service import CafeError, wallet, key, fingerprint, integer, ledger, audit
from app.services.cafe_slot_reservations import scheduled_slots, ensure_console_window, hold_slots, release_slots, local_window


def uid(): return str(uuid.uuid4())
def stamp(value): return value.isoformat()+'Z' if value else None

def ready():
    if db.engine.dialect.name == 'postgresql':
        return bool(db.session.execute(text("SELECT to_regclass('kiosk_runtime_sessions')")).scalar())
    return inspect(db.engine).has_table('kiosk_runtime_sessions')

def settings(vendor_id):
    row=db.session.get(SessionExtensionPolicy,vendor_id)
    return {'self_qr_credit_mode':row.credit_mode if row else 'automatic',
            'credit_limit_paise':row.credit_limit if row else None,'reminder_seconds':300}

def notice(row,kind,**details):
    dedupe=f"{row.id}:{kind}:{details.get('request_id') or row.reserved_until.isoformat()}"
    if not SessionNotice.query.filter_by(dedupe_key=dedupe).first():
        db.session.add(SessionNotice(id=uid(),vendor_id=row.vendor_id,runtime_id=row.id,
            kind=kind,details=details,dedupe_key=dedupe))

def debt(vendor_id,user_id):
    return int(db.session.query(db.func.coalesce(db.func.sum(ExtensionSegment.credit_due-ExtensionSegment.credit_paid),0))
        .join(RuntimeSession,RuntimeSession.id==ExtensionSegment.runtime_id)
        .filter(RuntimeSession.vendor_id==vendor_id,RuntimeSession.user_id==user_id,
                RuntimeSession.source_kind=='self_qr').scalar() or 0)

def segments(row):
    return ExtensionSegment.query.filter_by(runtime_id=row.id).order_by(ExtensionSegment.starts_at).all()

def snapshot(row):
    pending=ExtensionQuote.query.filter(ExtensionQuote.runtime_id==row.id,ExtensionQuote.status.in_(['approval_pending','conflict_pending','consent_required','credit_limit'])).order_by(ExtensionQuote.starts_at.desc()).first()
    parts=segments(row);total=sum(p.charged for p in parts);funded=sum(p.captured for p in parts)
    waived=sum(r.amount for r in SessionReceipt.query.filter_by(runtime_id=row.id,method='waiver').all())
    collected=sum(p.credit_paid for p in parts)-waived;now=datetime.utcnow()
    from app.models.cafe_wallet import CafeWallet
    w=db.session.get(CafeWallet,(row.vendor_id,row.user_id))
    return {'runtime_id':row.id,'session_ref':{'kind':row.source_kind,'id':row.source_id},
        'console_id':row.console_id,'vendor_id':row.vendor_id,'revision':row.revision,'event_sequence':row.event_sequence,'state':row.status,
        'server_time':stamp(now),'started_at':stamp(row.started_at),'paid_until':stamp(row.paid_until),
        'reserved_until':stamp(row.reserved_until),'stop_at':stamp(row.stop_at),'auto_lock_at_end':False,
        'play_allowed':row.ended_at is None and now<min(row.reserved_until,row.stop_at or row.reserved_until),
        'last_seen_at':stamp(row.last_seen_at),'ended_at':stamp(row.ended_at),'extension':{'mode':row.credit_mode,'rolling_enabled':row.rolling,'reason_code':row.reason,'request_id':pending.id if pending else None,'status':pending.status if pending else row.status,'requested_price_paise':pending.amount if pending else None},
        'billing':{'currency':'INR','payment_method':'pay_at_desk' if row.source_kind=='booking' else 'cafe_wallet',
          'has_extension':bool(parts),'payment_status':'amount_due' if total-funded-collected-waived>0 else 'extension_reserved' if row.ended_at is None and any(p.amount>p.funding+p.credit_paid for p in parts) else 'settled' if row.ended_at else 'prepaid',
          'total_paise':total,'wallet_funded_paise':funded,'collected_paise':collected,
          'waived_paise':waived,'credit_due_paise':total-funded-collected-waived,'amount_due_paise':total-funded-collected-waived,
          'net_cafe_balance_paise':(w.balance if w else 0)-debt(row.vendor_id,row.user_id),
          'as_of':stamp(row.billed_at),'is_final':row.ended_at is not None}}

def changed(row, state_changed=True, availability_changed=False):
    if state_changed: row.revision+=1
    row.event_sequence=(row.event_sequence or 0)+1
    db.session.flush()
    db.session.add(SessionOutbox(id=uid(),runtime_id=row.id,revision=row.revision,snapshot=dict(snapshot(row),availability_changed=availability_changed)))

def runtime_wallet(row):
    # Desk/app guests need an invoice, not a cafe wallet or app login.
    if row.source_kind=='self_qr':return wallet(row.vendor_id,row.user_id)
    from app.models.vendor import Vendor
    from app.models.cafe_wallet import CafeWallet
    if not Vendor.query.filter_by(id=row.vendor_id).populate_existing().with_for_update().first():raise CafeError('Cafe not found',404)
    existing=CafeWallet.query.filter_by(vendor_id=row.vendor_id,user_id=row.user_id).populate_existing().with_for_update().first()
    return existing or SimpleNamespace(vendor_id=row.vendor_id,user_id=row.user_id,balance=0,reserved=0)


def lock_row(runtime_id,vendor_id=None,link_id=None):
    initial=db.session.get(RuntimeSession,runtime_id)
    if not initial or (vendor_id is not None and initial.vendor_id!=vendor_id) or (link_id is not None and initial.link_id!=link_id):
        raise CafeError('Session not found',404)
    if db.engine.dialect.name=='postgresql':
        from app.services.kiosk_security import vendor_lock
        vendor_lock(initial.vendor_id)
    runtime_wallet(initial)
    return RuntimeSession.query.filter_by(id=runtime_id).populate_existing().with_for_update().one()

def attach(link,ref):
    if not isinstance(ref,dict) or ref.get('kind') not in ('booking','self_qr'):
        raise CafeError('Supply a valid session_ref')
    source=str(ref.get('id',''))
    old=RuntimeSession.query.filter_by(source_kind=ref['kind'],source_id=source,console_id=link.console_id).first()
    if old:
        return lock_row(old.id,link_id=link.id)
    if ref['kind']=='self_qr':
        qr=CafePlaySession.query.filter_by(id=source,link_id=link.id,state='active').first()
        if not qr or qr.kind!='wallet': raise CafeError('Active QR session required',409)
        user=qr.user_id;start=qr.started_at;end=qr.ends_at;bookings=[]
    else:
        from app.services.kiosk_runtime import booking_window
        from app.services.kiosk_security import KioskError
        try: window=booking_window(link.vendor_id,int(source),link.console_id)
        except (ValueError,KioskError): raise CafeError('Active assigned booking required',409)
        if window['status']!='active' or not window['user_id']: raise CafeError('Active assigned booking required',409)
        user=window['user_id'];start=datetime.fromisoformat(window['start_time']).astimezone(timezone.utc).replace(tzinfo=None)
        end=datetime.fromisoformat(window['end_time']).astimezone(timezone.utc).replace(tzinfo=None);bookings=window['booking_ids']
    if db.engine.dialect.name=='postgresql':
        from app.services.kiosk_security import vendor_lock
        vendor_lock(link.vendor_id)
    runtime_wallet(SimpleNamespace(source_kind=ref['kind'],vendor_id=link.vendor_id,user_id=user))
    Console.query.filter_by(id=link.console_id,vendor_id=link.vendor_id).with_for_update().one()
    old=RuntimeSession.query.filter_by(source_kind=ref['kind'],source_id=source,console_id=link.console_id).first()
    if old: return old
    if datetime.utcnow()>=end: raise CafeError('Enroll before the funded boundary; settle existing overtime first',409)
    occupied=RuntimeSession.query.filter_by(console_claim=link.console_id).first()
    if occupied:
        if ref['kind']=='booking' and occupied.source_kind=='booking' and int(source) in occupied.booking_ids:
            return occupied
        raise CafeError('This console already has an enrolled session',409)
    config=settings(link.vendor_id)
    row=RuntimeSession(id=uid(),vendor_id=link.vendor_id,console_id=link.console_id,link_id=link.id,user_id=user,console_claim=link.console_id,
        source_kind=ref['kind'],source_id=source,booking_ids=bookings,started_at=start,paid_until=end,reserved_until=end,
        credit_mode=config['self_qr_credit_mode'],credit_limit=config['credit_limit_paise'],revision=1,status='active',last_seen_at=datetime.utcnow())
    db.session.add(row);db.session.flush();changed(row)
    return row

def next_price(row):
    start=max(row.reserved_until,datetime.utcnow());local,_=local_window(start,start)
    # Infer the next schedule boundary from the authoritative dated slot grid.
    link=SimpleNamespace(vendor_id=row.vendor_id,console_id=row.console_id)
    rows=db.session.execute(text(f'''SELECT v.date,v.slot_id,v.available_slot,v.is_available,s.start_time,s.end_time
      FROM VENDOR_{int(row.vendor_id)}_SLOT v JOIN slots s ON s.id=v.slot_id
      JOIN available_game_console ac ON ac.available_game_id=s.gaming_type_id
      WHERE ac.console_id=:console AND v.vendor_id=:vendor AND v.date BETWEEN :first AND :last
      ORDER BY v.date,s.start_time'''),{'console':row.console_id,'vendor':row.vendor_id,
        'first':local.date()-timedelta(days=1),'last':local.date()+timedelta(days=1)}).mappings().all()
    from app.services.pricing_math import slot_window
    from app.services.cafe_slot_reservations import _day,_time
    candidates=[]
    for item in rows:
        left,right=slot_window(_day(item['date']),_time(item['start_time']),_time(item['end_time']))
        if left<=local<right: candidates.append((left,right))
    if len(candidates)!=1: raise CafeError('Console schedule overlaps or does not cover extension',409)
    right=candidates[0][1];seconds=max(1,math.ceil((right-local).total_seconds()))
    minutes=max(1,(seconds+59)//60)
    from app.services.cafe_session_pricing import session_prices
    actual_link=db.session.get(ConsoleLinkSession,row.link_id)
    prices=session_prices(actual_link,[{'minutes':minutes}],now=local.replace(second=0,microsecond=0),check_capacity=False,startup_buffer_seconds=0,check_console=False,allow_short_duration=True)
    if not prices or prices[0]['amount'] is None: raise CafeError(prices[0].get('unavailable_reason','Extension price unavailable') if prices else 'Extension price unavailable',409)
    # Prorate the final seconds rather than extending through the next grid boundary.
    amount=(prices[0]['amount']*seconds+minutes*60-1)//(minutes*60)
    return start,start+(right-local),amount

def quote(row):
    if row.ended_at: raise CafeError('Session ended',409)
    start,end,amount=next_price(row)
    q=ExtensionQuote(id=uid(),runtime_id=row.id,revision=row.revision,starts_at=start,ends_at=end,
        amount=amount,expires_at=datetime.utcnow()+timedelta(seconds=30),status='quoted')
    db.session.add(q);db.session.flush()
    w=runtime_wallet(row);fund=min(amount,max(0,w.balance-w.reserved)) if row.source_kind=='self_qr' else 0
    return q,{'quote_id':q.id,'revision':row.revision,'expires_at':stamp(q.expires_at),'interval_start':stamp(start),
        'interval_end':stamp(end),'price_paise':amount,'wallet_funded_paise':fund,'credit_paise':amount-fund,
        'self_qr_credit_mode':settings(row.vendor_id)['self_qr_credit_mode'],
        'credit_limit_paise':settings(row.vendor_id)['credit_limit_paise'],
        'requires_owner_approval':row.source_kind=='self_qr' and amount>fund and settings(row.vendor_id)['self_qr_credit_mode']=='owner_approval'}

def grant(row,q,owner=False):
    if row.ended_at or q.starts_at!=row.reserved_until: raise CafeError('Session or extension boundary changed',409)
    if row.last_seen_at<datetime.utcnow()-timedelta(seconds=60): raise CafeError('Kiosk is offline; reconnect before extending',409)
    w=runtime_wallet(row)
    if quoted_amount(row,q)!=q.amount: raise CafeError('Price changed; accept a fresh quote',409)
    Console.query.filter_by(id=row.console_id,vendor_id=row.vendor_id).with_for_update().one()
    active_link=ConsoleLinkSession.query.filter_by(id=row.link_id,status='active').with_for_update().first()
    if not active_link: raise CafeError('Kiosk link revoked',403)
    link=SimpleNamespace(vendor_id=row.vendor_id,console_id=row.console_id)
    start,end=local_window(q.starts_at,q.ends_at)
    try:
        ensure_console_window(link,start,end,exclude_bookings=row.booking_ids)
        slots=scheduled_slots(link,start,end,lock=True)
    except ValueError as exc: raise CafeError(str(exc),409) from exc
    claims=CafeSlotReservation.query.filter(CafeSlotReservation.session_id.in_([row.id,row.source_id]),CafeSlotReservation.released_at.is_(None)).all()
    held={(c.date,c.slot_id) for c in claims}
    new=[item for item in slots if (item['date'],item['slot_id']) not in held]
    config=settings(row.vendor_id)
    row.credit_mode=config['self_qr_credit_mode'];row.credit_limit=config['credit_limit_paise']
    fund=min(q.amount,max(0,w.balance-w.reserved)) if row.source_kind=='self_qr' else 0
    credit=q.amount-fund
    if row.source_kind=='self_qr' and credit:
        limit_hit=row.credit_limit is not None and credit_exposure(row)+credit>row.credit_limit
        approval_needed=row.credit_mode=='owner_approval' and not owner
        if not row.credit_consent or limit_hit or approval_needed:
            if fund>0:
                duration=max(1,math.ceil((q.ends_at-q.starts_at).total_seconds()))
                funded_seconds=int(duration*fund//q.amount)
                if funded_seconds>0:
                    basis=q.pricing_basis or {'start':stamp(q.starts_at),'end':stamp(q.ends_at),'amount':q.amount}
                    paid=(q.amount*funded_seconds+duration-1)//duration
                    funded_end=q.starts_at+timedelta(seconds=funded_seconds)
                    part_quote=ExtensionQuote(id=uid(),runtime_id=row.id,revision=row.revision,starts_at=q.starts_at,
                        ends_at=funded_end,amount=paid,expires_at=datetime.utcnow()+timedelta(seconds=30),pricing_basis=basis)
                    db.session.add(part_quote);db.session.flush()
                    grant(row,part_quote)
                    q.starts_at=funded_end;q.amount-=paid;q.pricing_basis=basis
                    q.status='consent_required' if not row.credit_consent else 'credit_limit' if limit_hit else 'approval_pending'
                    row.status=q.status;row.reason=q.status
                    notice(row,'approval_required' if q.status=='approval_pending' else q.status,request_id=q.id,amount=q.amount)
                    changed(row);return False
            if not row.credit_consent: raise CafeError('Credit consent required',409)
            if limit_hit: raise CafeError('Cafe credit limit reached',409)
            q.status='approval_pending';row.status='approval_pending';row.reason='owner_approval_required'
            notice(row,'approval_required',request_id=q.id,amount=q.amount);changed(row);return False
    try: hold_slots(SimpleNamespace(id=row.id,vendor_id=row.vendor_id),new)
    except ValueError as exc: raise CafeError(str(exc),409) from exc
    part=ExtensionSegment(id=uid(),runtime_id=row.id,starts_at=q.starts_at,ends_at=q.ends_at,amount=q.amount,
        funding=fund,captured=0,charged=0,credit_due=0,credit_paid=0,closed=False)
    db.session.add(part);w.reserved+=fund
    if fund:
        ledger(w,'extension_reserve',0,{'id':'runtime','name':'Session runtime'},'reserve-ext:'+part.id,
            fingerprint([part.id,fund]),session_id=row.source_id,reason='Reserved wallet funding for continuation')
    row.reserved_until=q.ends_at;row.status='active';row.reason=None;row.stop_at=None;q.status='granted'
    notice(row,'extension_granted',price_paise=q.amount,credit_authorized_paise=credit)
    if credit and row.source_kind=='self_qr': notice(row,'credit_authorized',amount_paise=credit)
    changed(row,availability_changed=True);return True

def accrue(row,now=None,close=False):
    now=min(now or datetime.utcnow(),row.ended_at or datetime.max,row.stop_at or datetime.max)
    w=runtime_wallet(row)
    for part in segments(row):
        if part.closed: continue
        seconds=max(0,min((now-part.starts_at).total_seconds(),(part.ends_at-part.starts_at).total_seconds()))
        duration=max(1,math.ceil((part.ends_at-part.starts_at).total_seconds()))
        used=part.amount if now>=part.ends_at else min(part.amount,(part.amount*math.ceil(seconds)+duration-1)//duration)
        used=max(part.charged,used)
        # New wallet funds pay future usage; never retroactively reclassify credit.
        if row.source_kind=='self_qr' and now>=part.starts_at:
            remaining=part.amount-part.charged if not close else used-part.charged
            extra=min(max(0,w.balance-w.reserved),max(0,remaining-(part.funding-part.captured)))
            if extra:
                part.funding+=extra;w.reserved+=extra
                ledger(w,'extension_reserve',0,{'id':'runtime','name':'Session runtime'},f'refund-ext:{part.id}:{part.funding}',
                    fingerprint([part.id,part.funding]),session_id=row.source_id,reason='Wallet funding for future continuation usage')
        delta=min(used-part.charged,part.funding-part.captured)
        funded=part.captured+delta
        if delta:
            w.balance-=delta;w.reserved-=delta;part.captured=funded
            ledger(w,'extension_capture',-delta,{'id':'runtime','name':'Session runtime'},f'ext:{part.id}:{funded}',
                fingerprint([part.id,funded]),session_id=row.source_id,reason='Metered session extension')
        credit_delta=used-funded-part.credit_due
        if credit_delta:
            if row.source_kind=='self_qr' and part.credit_due==0: notice(row,'wallet_exhausted',amount_due_paise=credit_delta)
            db.session.add(SessionCreditEntry(id=uid(),runtime_id=row.id,segment_id=part.id,amount=credit_delta,kind='charge',
                idempotency_key=f'credit:{part.id}:{used-funded}'))
        part.charged=used;part.credit_due=used-funded
        if close or now>=part.ends_at:
            unused=part.funding-part.captured
            w.reserved-=unused;part.closed=True
            if unused: ledger(w,'extension_release',0,{'id':'runtime','name':'Session runtime'},'release-ext:'+part.id,
                fingerprint([part.id,unused]),session_id=row.source_id,reason='Unused continuation wallet funding released')
    row.billed_at=now
    db.session.flush()

def finish(row,at=None):
    if row.ended_at: return row
    row.ended_at=min(at or datetime.utcnow(),row.reserved_until,row.stop_at or datetime.max)
    accrue(row,row.ended_at,close=True);row.rolling=False;row.console_claim=None;row.status='ended_unsettled';row.stop_at=row.ended_at
    for pending in ExtensionQuote.query.filter(ExtensionQuote.runtime_id==row.id,ExtensionQuote.status.in_(['approval_pending','conflict_pending','consent_required','credit_limit'])).all():
        pending.status='cancelled' if row.ended_at<pending.starts_at else 'expired'
    release_slots(SimpleNamespace(id=row.id,vendor_id=row.vendor_id))
    if row.source_kind=='self_qr':
        qr=db.session.get(CafePlaySession,row.source_id)
        if qr and qr.state=='active':
            from app.services.cafe_wallet_service import release_console
            qr.state='completed';qr.ended_at=row.ended_at;qr.due_amount=sum(p.credit_due-p.credit_paid for p in segments(row));release_console(qr)
    else:
        from app.services.kiosk_runtime import assigned_consoles
        from app.models.booking import Booking
        for bid in row.booking_ids:
            booking=Booking.query.filter_by(id=bid).populate_existing().with_for_update().first()
            if not booking: continue
            details=dict(booking.squad_details or {})
            assigned=set(int(x) for x in details.get('assigned_console_ids',[]) or [row.console_id])
            released=set(int(x) for x in details.get('released_console_ids',[]));released.add(row.console_id)
            details['released_console_ids']=sorted(released)
            release_base_booking(row,booking,details,assigned,released)
            booking.squad_details=details
            if assigned<=released:
                booking.status='completed'
                db.session.execute(text(f"UPDATE VENDOR_{int(row.vendor_id)}_DASHBOARD SET book_status='completed' WHERE book_id=:bid"),{'bid':bid})
        from app.models.cafe_wallet import CafeBookingClaim
        for qr in CafePlaySession.query.join(CafeBookingClaim,CafeBookingClaim.session_id==CafePlaySession.id).filter(
                CafePlaySession.vendor_id==row.vendor_id,CafePlaySession.console_id==row.console_id,
                CafePlaySession.kind=='existing_booking',CafePlaySession.state=='active',
                CafeBookingClaim.booking_id.in_(row.booking_ids)).all():
            from app.services.cafe_wallet_service import release_console
            qr.state='completed';qr.ended_at=row.ended_at;release_console(qr)
        if db.engine.dialect.name=='postgresql':
            db.session.execute(text(f'UPDATE VENDOR_{int(row.vendor_id)}_CONSOLE_AVAILABILITY SET is_available=true WHERE console_id=:cid'),{'cid':row.console_id})
    due=sum(p.credit_due-p.credit_paid for p in segments(row))
    if not due: row.status='settled'
    notice(row,'session_ended',amount_due_paise=due);changed(row,availability_changed=True)
    return row

def continue_session(row,qid,body):
    idem=key(body.get('idempotency_key'));fp=fingerprint([row.id,qid,body.get('credit_consent')])
    replay=ExtensionQuote.query.filter_by(idempotency_key=idem).first()
    if replay:
        if replay.runtime_id!=row.id or replay.fingerprint!=fp: raise CafeError('Idempotency conflict',409)
        return replay
    if type(body.get('credit_consent',False)) is not bool: raise CafeError('credit_consent must be boolean')
    q=ExtensionQuote.query.filter_by(id=qid,runtime_id=row.id).with_for_update().first()
    if not q or q.status!='quoted' or q.expires_at<=datetime.utcnow(): raise CafeError('Quote expired',409)
    if row.revision!=body.get('revision') or q.revision!=row.revision: raise CafeError('Stale session revision',409)
    for old in ExtensionQuote.query.filter(ExtensionQuote.runtime_id==row.id,ExtensionQuote.id!=q.id,ExtensionQuote.status.in_(['approval_pending','conflict_pending','consent_required','credit_limit'])).all():
        old.status='superseded'
    row.rolling=True;row.credit_consent=body.get('credit_consent',False)
    audit(row.vendor_id,{'id':f'kiosk-{row.link_id}','name':f'PC {row.console_id}'},'extension.continue_requested',
        {'runtime_id':row.id,'quote_id':q.id,'credit_consent':row.credit_consent})
    q.idempotency_key=idem;q.fingerprint=fp
    try:
        with db.session.begin_nested(): grant(row,q)
    except (ValueError,CafeError) as exc:
        if isinstance(exc,CafeError) and ('Price changed' in exc.message):
            raise
        if isinstance(exc,CafeError) and ('consent' in str(exc.message).lower() or 'credit limit' in str(exc.message).lower()):
            raise
        row.status='conflict_pending';row.reason='staff_resolution_required';q.status='conflict_pending'
        notice(row,'extension_conflict',request_id=q.id);changed(row)
    return q

def receipt(row,body,actor):
    idem=key(body.get('idempotency_key'));amount=integer(body.get('amount_paise'))
    method=body.get('method');reason=str(body.get('reason') or '').strip();fp=fingerprint([row.id,amount,method,reason])
    old=SessionReceipt.query.filter_by(vendor_id=row.vendor_id,idempotency_key=idem).first()
    if old:
        if old.fingerprint!=fp or old.actor_id!=actor['id']: raise CafeError('Idempotency conflict',409)
        return old
    if not row.ended_at or body.get('revision')!=row.revision: raise CafeError('Refresh final settlement summary',409)
    if method not in ('cash','card','cafe_upi','upi','waiver'): raise CafeError('Choose a supported collection method')
    shift=CafeShift.query.filter_by(open_key=f"{row.vendor_id}:{actor['id']}").first()
    if method!='waiver' and not shift: raise CafeError('Open your shift before collecting payment',409)
    if method=='waiver' and not 3<=len(reason)<=500: raise CafeError('A waiver reason of 3–500 characters is required')
    due=sum(p.credit_due-p.credit_paid for p in segments(row))
    if amount>due: raise CafeError('Collection exceeds remaining due',409)
    remaining=amount
    for part in segments(row):
        allocated=min(remaining,part.credit_due-part.credit_paid);part.credit_paid+=allocated;remaining-=allocated
        if allocated: db.session.add(SessionCreditEntry(id=uid(),runtime_id=row.id,segment_id=part.id,amount=-allocated,kind='waiver' if method=='waiver' else 'payment',
            idempotency_key='payment:'+fingerprint([idem,part.id])[:64]))
    w=runtime_wallet(row)
    result=SessionReceipt(id=uid(),runtime_id=row.id,vendor_id=row.vendor_id,amount=amount,method=method,
        actor_id=actor['id'],idempotency_key=idem,fingerprint=fp)
    db.session.add(result)
    ledger(w,'credit_waiver' if method=='waiver' else 'session_collection',0 if method=='waiver' else amount,actor,idem,fp,method=method,shift_id=shift.id if shift else None,
        session_id=row.source_id,reason=reason if method=='waiver' else 'Session extension collection')
    if due==amount: row.status='settled'
    if row.source_kind=='self_qr':
        qr=db.session.get(CafePlaySession,row.source_id)
        if qr: qr.due_amount=due-amount;qr.settled_at=datetime.utcnow() if due==amount else None
    changed(row);audit(row.vendor_id,actor,'extension.settled',{'runtime_id':row.id,'amount':amount})
    return result


def tick():
    from app.services.session_realtime import expire_gamer_connections
    expire_gamer_connections()
    if not ready(): db.session.rollback();return
    ids=[r.id for r in RuntimeSession.query.filter_by(ended_at=None).all()];db.session.rollback()
    for rid in ids:
        try:
            row=lock_row(rid);now=datetime.utcnow()
            previous_charge=sum(p.charged for p in segments(row));previous_sequence=row.event_sequence
            accrue(row,now)
            link=db.session.get(ConsoleLinkSession,row.link_id)
            if not link or link.status!='active':
                finish(row,now);db.session.commit();continue
            if row.source_kind=='self_qr':
                source=db.session.get(CafePlaySession,row.source_id)
                if not source or source.state!='active':
                    finish(row,now);db.session.commit();continue
            else:
                statuses=db.session.execute(text('SELECT status FROM bookings WHERE id IN :ids').bindparams(__import__('sqlalchemy').bindparam('ids',expanding=True)),{'ids':row.booking_ids}).scalars().all()
                if not statuses or all(s in ('cancelled','canceled','completed') for s in statuses):
                    finish(row,now);db.session.commit();continue
            if row.stop_at and now>=row.stop_at: finish(row,row.stop_at)
            elif now>=row.reserved_until: finish(row,row.reserved_until)
            elif row.last_seen_at<now-timedelta(seconds=60):
                if row.status!='offline':
                    row.status='offline';row.reason='kiosk_offline';notice(row,'kiosk_offline');changed(row)
            elif row.rolling and row.status in ('approval_pending','credit_limit','consent_required'):
                pending=ExtensionQuote.query.filter(ExtensionQuote.runtime_id==row.id,ExtensionQuote.status.in_(['approval_pending','credit_limit','consent_required'])).first()
                config=settings(row.vendor_id);w=runtime_wallet(row)
                if pending and (w.balance>w.reserved or (row.credit_consent and (config['self_qr_credit_mode']=='automatic' or row.status=='credit_limit') and (config['credit_limit_paise'] is None or credit_exposure(row)+pending.amount<=config['credit_limit_paise']))):
                    try:
                        with db.session.begin_nested(): grant(row,pending)
                    except CafeError as exc:
                        row.reason='price_changed' if 'Price changed' in exc.message else 'staff_resolution_required'
                        row.status='price_changed' if row.reason=='price_changed' else 'conflict_pending'
                        pending.status=row.status;notice(row,row.status,request_id=pending.id);changed(row)
            elif row.rolling and row.reserved_until<=now+timedelta(minutes=5) and row.status=='active':
                q,_=quote(row)
                previous=segments(row)
                last=previous[-1] if previous else None
                if last and abs(q.amount-(last.amount*max(1,math.ceil((q.ends_at-q.starts_at).total_seconds()))+max(1,math.ceil((last.ends_at-last.starts_at).total_seconds()))-1)//max(1,math.ceil((last.ends_at-last.starts_at).total_seconds())))>1:
                    q.status='price_changed';row.status='price_changed';row.reason='price_changed'
                    notice(row,'price_changed');changed(row);db.session.commit();continue
                try:
                    with db.session.begin_nested(): grant(row,q)
                except (CafeError,ValueError):
                    q.status='conflict_pending';row.status='conflict_pending';row.reason='staff_resolution_required'
                    notice(row,'extension_conflict',request_id=q.id);changed(row)
            else:
                if row.reserved_until<=now+timedelta(minutes=5) and row.notice_boundary!=row.reserved_until:
                    row.notice_boundary=row.reserved_until;notice(row,'time_low');changed(row)
                elif sum(p.charged for p in segments(row))!=previous_charge: changed(row,state_changed=False)
            if row.event_sequence==previous_sequence and sum(p.charged for p in segments(row))!=previous_charge: changed(row,state_changed=False)
            db.session.commit()
        except Exception:
            db.session.rollback();current_app.logger.exception('Extension reconciliation failed runtime=%s',rid)
    dispatch()


def dispatch():
    if not ready(): db.session.rollback();return
    from app.services.websocket_service import socketio
    ids=[r.id for r in SessionOutbox.query.filter_by(published_at=None).order_by(SessionOutbox.created_at).limit(100).all()]
    db.session.rollback()
    for eid in ids:
        try:
            event=SessionOutbox.query.filter_by(id=eid,published_at=None).with_for_update(skip_locked=True).first()
            if not event: db.session.rollback();continue
            row=db.session.get(RuntimeSession,event.runtime_id)
            try:
                from app.routes import _invalidate_vendor_caches
                _invalidate_vendor_caches(row.vendor_id)
            except ImportError: pass
            payload={'event_id':event.id,'session_ref':event.snapshot['session_ref'],'revision':event.revision,
                     'server_time':stamp(datetime.utcnow()),'event_sequence':event.snapshot['event_sequence'],'snapshot':event.snapshot}
            staff_event={k:payload[k] for k in ('event_id','revision','event_sequence','server_time')}
            staff_event.update(vendor_id=row.vendor_id,console_id=row.console_id,runtime_id=row.id)
            socketio.emit('session.updated',staff_event,room=f'vendor_{row.vendor_id}')
            socketio.emit('session.updated',payload,room=f'cafe-user:{row.user_id}',namespace='/cafe-gamer')
            link=db.session.get(ConsoleLinkSession,row.link_id)
            next_player=RuntimeSession.query.filter(RuntimeSession.console_id==row.console_id,RuntimeSession.ended_at.is_(None),RuntimeSession.id!=row.id).first()
            if link and link.status=='active' and not next_player:
                socketio.emit('session.updated',payload,room=f'kiosk_link_{row.link_id}')
                socketio.emit('session.updated',payload,to=f'cafe-agent:{row.link_id}',namespace='/cafe-agent')
            if row.source_kind=='self_qr':
                from app.services.cafe_continuation_service import snapshot as qr_snapshot
                qr=db.session.get(CafePlaySession,row.source_id)
                if qr: socketio.emit('cafe_session_updated',qr_snapshot(qr),room=f'vendor_{row.vendor_id}')
            if event.snapshot.get('availability_changed'):
                socketio.emit('slots.updated',{'vendor_id':row.vendor_id,'event_id':event.id,'server_time':payload['server_time']},room=f'public-cafe:{row.vendor_id}',namespace='/cafe-availability')
                socketio.emit('booking_slots_updated',{'vendor_id':row.vendor_id,'console_id':row.console_id},room=f'vendor_{row.vendor_id}')
                socketio.emit('console_availability',{'vendor_id':row.vendor_id,'console_id':row.console_id,'is_available':row.ended_at is not None},room=f'vendor_{row.vendor_id}')
            event.published_at=datetime.utcnow();db.session.commit()
        except Exception:
            db.session.rollback();current_app.logger.exception('Extension event dispatch failed event=%s',eid)


def stop(row,body):
    from app.models.session_extension import RuntimeMutation
    idem=key(body.get('idempotency_key'));mode=body.get('mode','now');fp=fingerprint([row.id,mode])
    old=db.session.get(RuntimeMutation,(row.id,idem))
    if old:
        if old.fingerprint!=fp: raise CafeError('Idempotency conflict',409)
        return row
    if mode not in ('now','at_authorized_end'): raise CafeError('Choose now or at_authorized_end')
    if mode=='at_authorized_end' and not row.ended_at and body.get('revision')!=row.revision: raise CafeError('Stale session revision',409)
    db.session.add(RuntimeMutation(runtime_id=row.id,idempotency_key=idem,fingerprint=fp))
    if mode=='now': finish(row)
    elif not row.ended_at:
        row.rolling=False;row.stop_at=row.reserved_until
        for pending in ExtensionQuote.query.filter(ExtensionQuote.runtime_id==row.id,ExtensionQuote.status.in_(['approval_pending','conflict_pending','consent_required','credit_limit'])).all(): pending.status='cancelled'
        changed(row)
    return row


def decide(row,q,body,actor):
    from app.models.session_extension import RuntimeMutation
    idem=key(body.get('idempotency_key'));choice=body.get('decision');fp=fingerprint([row.id,q.id,choice])
    old=db.session.get(RuntimeMutation,(row.id,idem))
    if old:
        if old.fingerprint!=fp: raise CafeError('Idempotency conflict',409)
        return row
    if choice not in ('approve','retry','reject'): raise CafeError('Choose approve, retry or reject')
    if row.ended_at or q.status not in ('approval_pending','conflict_pending') or body.get('revision')!=row.revision:
        raise CafeError('Request/session changed. Refresh.',409)
    if q.status=='approval_pending' and choice=='retry': raise CafeError('Only approval can grant requested credit',403)
    if q.starts_at<datetime.utcnow(): raise CafeError('Authorization boundary passed',409)
    db.session.add(RuntimeMutation(runtime_id=row.id,idempotency_key=idem,fingerprint=fp))
    if choice=='reject':
        q.status='rejected';row.rolling=False;row.status='active';row.reason='request_rejected';notice(row,'extension_rejected');changed(row)
    else:
        grant(row,q,owner=choice=='approve')
    audit(row.vendor_id,actor,'extension.decision',{'runtime_id':row.id,'request_id':q.id,'decision':choice})


def repay_from_topup(w,amount,actor,idem):
    """Allocate a desk top-up to existing cafe debt before spendable funds."""
    if not ready(): return 0
    remaining=amount;paid=0
    rows=RuntimeSession.query.filter_by(vendor_id=w.vendor_id,user_id=w.user_id,source_kind='self_qr').order_by(RuntimeSession.started_at).all()
    for row in rows:
        allocations=0
        for part in segments(row):
            allocated=min(remaining,part.credit_due-part.credit_paid)
            if not allocated: continue
            part.credit_paid+=allocated;remaining-=allocated;paid+=allocated;allocations+=allocated
            db.session.add(SessionCreditEntry(id=uid(),runtime_id=row.id,segment_id=part.id,amount=-allocated,kind='topup_payment',
                idempotency_key='topup:'+fingerprint([idem,part.id])[:64]))
        if allocations:
            w.balance-=allocations
            ledger(w,'credit_repayment',-allocations,actor,'debt:'+fingerprint([idem,row.id])[:64],
                fingerprint([idem,row.id,allocations]),session_id=row.source_id,reason='Top-up allocated to cafe credit')
            db.session.add(SessionReceipt(id=uid(),runtime_id=row.id,vendor_id=w.vendor_id,amount=allocations,
                method='topup',actor_id=actor['id'],idempotency_key='topup:'+fingerprint([idem,row.id])[:64],fingerprint=fingerprint([row.id,allocations,idem])))
            if row.ended_at and sum(p.credit_due-p.credit_paid for p in segments(row))==0: row.status='settled'
            qr=db.session.get(CafePlaySession,row.source_id)
            if qr and qr.state=='completed':
                qr.due_amount=sum(p.credit_due-p.credit_paid for p in segments(row))
                if not qr.due_amount: qr.settled_at=datetime.utcnow()
            changed(row)
        if not remaining: break
    return paid


def start_worker(app,socketio):
    """Independent of legacy expiry feature flags; multiple workers serialize rows."""
    if app.config.get('TESTING') or not app.config.get('SESSION_EXTENSION_WORKER_ENABLED',True): return
    def worker():
        while True:
            with app.app_context():
                try: tick()
                except Exception:
                    db.session.rollback();app.logger.exception('Session extension worker failed')
                finally: db.session.remove()
            socketio.sleep(5)
    socketio.start_background_task(worker)


def credit_exposure(row):
    parts=ExtensionSegment.query.join(RuntimeSession,RuntimeSession.id==ExtensionSegment.runtime_id).filter(
        RuntimeSession.vendor_id==row.vendor_id,RuntimeSession.user_id==row.user_id,RuntimeSession.source_kind=='self_qr').all()
    return sum((p.credit_due if p.closed else p.amount-p.funding)-p.credit_paid for p in parts)


def quoted_amount(row,q):
    if q.pricing_basis:
        basis=q.pricing_basis
        original=SimpleNamespace(starts_at=datetime.fromisoformat(basis['start'].removesuffix('Z')),
            ends_at=datetime.fromisoformat(basis['end'].removesuffix('Z')),pricing_basis=None)
        return q.amount if quoted_amount(row,original)==basis['amount'] else None
    from app.services.cafe_session_pricing import session_prices
    local,_=local_window(q.starts_at,q.starts_at);seconds=max(1,math.ceil((q.ends_at-q.starts_at).total_seconds()));minutes=max(1,(seconds+59)//60)
    prices=session_prices(db.session.get(ConsoleLinkSession,row.link_id),[{'minutes':minutes}],now=local.replace(second=0,microsecond=0),
        check_capacity=False,startup_buffer_seconds=0,check_console=False,allow_short_duration=True)
    value=prices[0]['amount'] if prices else None
    return None if value is None else (value*seconds+minutes*60-1)//(minutes*60)


def seen(row):
    if row.ended_at:return
    row.last_seen_at=datetime.utcnow()
    if row.status=='offline':
        pending=ExtensionQuote.query.filter(ExtensionQuote.runtime_id==row.id,ExtensionQuote.status.in_(['approval_pending','conflict_pending','consent_required','credit_limit'])).first()
        row.status=pending.status if pending else 'active'
        row.reason='staff_resolution_required' if pending else None
        changed(row)


def release_base_booking(row,booking,details,assigned,released):
    """One base capacity release per booking/device, shared with cancellation paths."""
    from app.models.session_extension import BaseSlotRelease
    from app.services.slot_capacity import booking_units,release_slot
    if db.session.get(BaseSlotRelease,(booking.id,row.console_id)) or not booking.slot_id:return
    baseline=dict(details);baseline.pop('remaining_slot_units',None)
    total=int(details.get('initial_slot_units',booking_units(baseline)))
    remaining=int(details.get('remaining_slot_units',total))
    if remaining<=0:return
    units=remaining if assigned<=released else min(remaining,max(0,total//max(1,len(assigned))))
    if not units:return
    day=db.session.execute(text(f'SELECT date FROM VENDOR_{int(row.vendor_id)}_DASHBOARD WHERE book_id=:bid'),{'bid':booking.id}).scalar()
    if not day:raise CafeError('Original booking date is missing; cannot release capacity',409)
    release_slot(db.session,row.vendor_id,booking.slot_id,day,units)
    details['initial_slot_units']=total;details['remaining_slot_units']=remaining-units
    db.session.add(BaseSlotRelease(booking_id=booking.id,console_id=row.console_id,runtime_id=row.id,units=units))


def financial_totals(vendor_id,day):
    """Extension revenue once at capture/accrual; collections are not new revenue."""
    import pytz
    from app.models.cafe_wallet import CafeLedger
    zone=pytz.timezone('Asia/Kolkata')
    begin=zone.localize(datetime.combine(day,datetime.min.time())).astimezone(timezone.utc).replace(tzinfo=None)
    end=begin+timedelta(days=1)
    captured=db.session.query(db.func.coalesce(db.func.sum(-CafeLedger.amount),0)).filter(
        CafeLedger.vendor_id==vendor_id,CafeLedger.kind=='extension_capture',CafeLedger.created_at>=begin,CafeLedger.created_at<end).scalar() or 0
    credit=db.session.query(db.func.coalesce(db.func.sum(SessionCreditEntry.amount),0)).join(
        RuntimeSession,RuntimeSession.id==SessionCreditEntry.runtime_id).filter(
        RuntimeSession.vendor_id==vendor_id,SessionCreditEntry.kind.in_(['charge','waiver']),
        SessionCreditEntry.created_at>=begin,SessionCreditEntry.created_at<end).scalar() or 0
    pending=db.session.query(db.func.coalesce(db.func.sum(ExtensionSegment.credit_due-ExtensionSegment.credit_paid),0)).join(
        RuntimeSession,RuntimeSession.id==ExtensionSegment.runtime_id).filter(RuntimeSession.vendor_id==vendor_id).scalar() or 0
    return {'earned_paise':int(captured+credit),'pending_paise':int(pending)}
