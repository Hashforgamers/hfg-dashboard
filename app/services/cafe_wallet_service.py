"""Transactional cafe checkout. Callers commit before publishing commands."""
from datetime import datetime, timedelta
import hashlib
import json
import secrets
import uuid
from sqlalchemy import func
from app.extension.extensions import db
from app.models.cafe_wallet import (
    CafePaymentPolicy, CafeWallet, CafeLedger, CafeAudit, CafeShift, CafePlaySession,
    CafeStaffSession,
)

DEFAULT_POLICY = {
    'gaming_methods': ['cafe_wallet'], 'topup_channels': ['desk'],
    'desk_methods': ['cash', 'cafe_upi'], 'hash_online_collection': False,
    'self_service': False, 'food_ordering': True, 'food_collection': 'vendor',
    'durations': [{'minutes': 60}],
}


class CafeError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


def integer(value, minimum=1, maximum=100000000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise CafeError('Invalid integer amount, duration or identifier')
    return value


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def key(value):
    if not isinstance(value, str) or not 8 <= len(value) <= 100:
        raise CafeError('An idempotency key of 8–100 characters is required')
    return value


def policy(vendor_id):
    row = db.session.get(CafePaymentPolicy, vendor_id)
    settings = dict(row.settings) if row else dict(DEFAULT_POLICY)
    settings['durations'] = [{'minutes':item['minutes']} for item in settings['durations']]
    return settings


def validate_policy(data):
    if not isinstance(data, dict) or set(data) != set(DEFAULT_POLICY):
        raise CafeError('Supply all supported payment policy fields')
    # Only offer payment rails actually implemented by this checkout.
    if data['gaming_methods'] != ['cafe_wallet'] or data['topup_channels'] != ['desk']:
        raise CafeError('Cafe checkout currently supports cafe wallet and desk top-ups only')
    if data['hash_online_collection'] is not False:
        raise CafeError('Online collection is not supported by cafe checkout')
    if type(data['self_service']) is not bool or type(data['food_ordering']) is not bool:
        raise CafeError('Feature settings must be boolean')
    if data['food_collection'] not in ('cafe', 'vendor'):
        raise CafeError('Invalid food collection mode')
    if not isinstance(data['desk_methods'], list) or not data['desk_methods'] or any(
        m not in ('cash', 'cafe_upi') for m in data['desk_methods']
    ) or len(set(data['desk_methods'])) != len(data['desk_methods']):
        raise CafeError('Choose cash and/or cafe UPI')
    if not isinstance(data['durations'], list) or not 1 <= len(data['durations']) <= 12:
        raise CafeError('Supply 1–12 session durations')
    seen = set()
    for item in data['durations']:
        if not isinstance(item, dict) or set(item) not in ({'minutes'}, {'minutes', 'amount'}):
            raise CafeError('Each duration requires minutes; prices come from Console Pricing')
        minutes = integer(item['minutes'], 5, 720)
        if minutes in seen:
            raise CafeError('Duplicate duration')
        seen.add(minutes)
    return dict(data, durations=[{'minutes':item['minutes']} for item in data['durations']])


def audit(vendor_id, actor, action, details):
    db.session.add(CafeAudit(vendor_id=vendor_id, actor_id=actor['id'],
                            actor_name=actor['name'], action=action, details=details))


def wallet(vendor_id, user_id):
    # Vendor row serializes first account creation and all money operations within a cafe.
    # This also gives checkout, settings and shift closure a consistent lock order.
    from app.models.vendor import Vendor
    if not Vendor.query.filter_by(id=vendor_id).populate_existing().with_for_update().first():
        raise CafeError('Cafe not found', 404)
    row = CafeWallet.query.filter_by(vendor_id=vendor_id, user_id=user_id).populate_existing().with_for_update().first()
    if row is None:
        row = CafeWallet(vendor_id=vendor_id, user_id=user_id, balance=0, reserved=0)
        db.session.add(row)
        db.session.flush()
    return row


def ledger(w, kind, amount, actor, idem, fp, **kwargs):
    row = CafeLedger(vendor_id=w.vendor_id, user_id=w.user_id, kind=kind, amount=amount,
                     balance_after=w.balance, reserved_after=w.reserved,
                     actor_id=actor['id'], actor_name=actor['name'],
                     idempotency_key=idem, fingerprint=fp, **kwargs)
    db.session.add(row)
    return row


def topup(vendor_id, user_id, body, actor):
    amount = integer(body.get('amount'))
    idem = key(body.get('idempotency_key'))
    method = body.get('method')
    fp = fingerprint([user_id, amount, method])
    w = wallet(vendor_id, user_id)
    existing = CafeLedger.query.filter_by(vendor_id=vendor_id, idempotency_key=idem).first()
    if existing:
        if existing.fingerprint != fp or existing.actor_id != actor['id']:
            raise CafeError('Idempotency key already used for another request', 409)
        return existing
    from app.services.payment_methods import require_method
    try:
        require_method(vendor_id, 'cafe_wallet')
    except ValueError as error:
        raise CafeError(str(error), 403)
    if method not in policy(vendor_id)['desk_methods']:
        raise CafeError('This desk payment method is disabled', 403)
    shift = CafeShift.query.filter_by(open_key=f"{vendor_id}:{actor['id']}").first()
    if not shift:
        raise CafeError('Open your shift before collecting money', 409)
    from app.models.user import User
    if not db.session.get(User, user_id):
        raise CafeError('Gamer not found', 404)
    w.balance += amount
    return ledger(w, 'topup', amount, actor, idem, fp, method=method,
                  shift_id=shift.id, reason='Desk top-up')


def refund(vendor_id, entry_id, body, actor):
    original = CafeLedger.query.filter_by(id=entry_id, vendor_id=vendor_id).first()
    if not original or original.kind not in ('topup', 'capture'):
        raise CafeError('Only a top-up or gaming charge can be reversed', 400)
    idem = key(body.get('idempotency_key'))
    reason = str(body.get('reason') or '').strip()
    if not 3 <= len(reason) <= 500:
        raise CafeError('A refund reason is required')
    w = wallet(vendor_id, original.user_id)
    previous = CafeLedger.query.filter_by(reversal_of=original.id).first()
    if previous:
        if previous.idempotency_key == idem and previous.actor_id == actor['id'] and previous.fingerprint == fingerprint([entry_id, reason]):
            return previous
        raise CafeError('Transaction already reversed', 409)
    delta = -original.amount
    if w.balance + delta < w.reserved:
        raise CafeError('Insufficient available balance for reversal', 409)
    shift = CafeShift.query.filter_by(open_key=f"{vendor_id}:{actor['id']}").first()
    if original.kind == 'topup' and not shift:
        raise CafeError('Open a shift before returning a desk payment', 409)
    w.balance += delta
    return ledger(w, 'refund', delta, actor, idem, fingerprint([entry_id, reason]),
                  reason=reason, reversal_of=original.id, session_id=original.session_id,
                  method=original.method, shift_id=shift.id if shift else None)


def reserve(vendor_id, user_id, link, minutes, idem, expected_amount=None, *, owner_credit=False, use_available_balance=False):
    integer(minutes, 5, 720)
    key(idem)
    fp = fingerprint([link.console_id, minutes])
    w = wallet(vendor_id, user_id)
    existing = CafePlaySession.query.filter_by(vendor_id=vendor_id, user_id=user_id,
                                                idempotency_key=idem).first()
    if existing:
        if existing.fingerprint != fp:
            raise CafeError('Idempotency key already used for another checkout', 409)
        return existing
    if not owner_credit and CafePlaySession.query.filter_by(vendor_id=vendor_id,user_id=user_id).filter(
        CafePlaySession.due_amount > 0, CafePlaySession.settled_at.is_(None)).first():
        raise CafeError('Settle the outstanding gaming balance at the desk before a new checkout',409)
    from app.services.payment_methods import require_method
    try:
        require_method(vendor_id, 'cafe_wallet')
    except ValueError as error:
        raise CafeError(str(error), 403)
    settings = policy(vendor_id)
    if not settings['self_service']:
        raise CafeError('Self-service is disabled at this cafe', 403)
    from app.services.cafe_session_pricing import session_prices, console_durations
    try:
        durations = console_durations(link)
        if use_available_balance:
            if not durations or minutes > max(d['minutes'] for d in durations):
                raise CafeError('This duration exceeds the cafe session limit',409)
            durations = [{'minutes':minutes}]
        quote = next((d for d in session_prices(link, durations) if d['minutes'] == minutes), None)
    except ValueError as error:
        raise CafeError(str(error), 409)
    price = quote['amount'] if quote else None
    if price is None:
        raise CafeError((quote or {}).get('unavailable_reason') or 'This duration is no longer available', 409)
    if expected_amount is not None and expected_amount != price:
        raise CafeError('Price changed. Reload checkout before paying.', 409)
    from app.services.cafe_slot_reservations import scheduled_slots, ensure_console_window, hold_slots, local_window
    now = datetime.utcnow()
    deadline = now + timedelta(seconds=45)
    # Cover the full paid duration even when PC acknowledgement takes 45 seconds.
    start, end = local_window(now, deadline + timedelta(minutes=minutes))
    try:
        slots = scheduled_slots(link, start, end, lock=True)
    except ValueError as error:
        raise CafeError(str(error), 409)
    from app.models.console import Console
    console = Console.query.filter_by(id=link.console_id, vendor_id=vendor_id).populate_existing().with_for_update().first()
    from app.models.console_link_session import ConsoleLinkSession
    link = ConsoleLinkSession.query.filter_by(id=link.id).populate_existing().with_for_update().first()
    if not console or not link or link.status != 'active':
        raise CafeError('PC is not linked', 409)
    if CafePlaySession.query.filter_by(console_claim=console.id).first():
        raise CafeError('PC is already reserved or playing', 409)
    try:
        ensure_console_window(link, start, end)
    except ValueError as error:
        raise CafeError(str(error), 409)
    # Existing dashboard assignments remain the authority for legacy bookings.
    from sqlalchemy import text
    if db.engine.dialect.name == 'postgresql':
        busy = db.session.execute(text(f'SELECT is_available FROM VENDOR_{int(vendor_id)}_CONSOLE_AVAILABILITY WHERE console_id = :cid FOR UPDATE'), {'cid': console.id}).all()
        if not busy or not all(row[0] for row in busy):
            raise CafeError('PC is unavailable', 409)
        db.session.execute(text(f'UPDATE VENDOR_{int(vendor_id)}_CONSOLE_AVAILABILITY SET is_available = false WHERE console_id = :cid'), {'cid': console.id})
    if not owner_credit and w.balance - w.reserved < price:
        raise CafeError('Insufficient cafe balance. Please top up at the desk.', 409)
    session = CafePlaySession(id=str(uuid.uuid4()), vendor_id=vendor_id, user_id=user_id,
        console_id=console.id, link_id=link.id, console_claim=console.id,
        idempotency_key=idem, fingerprint=fp, amount=price, minutes=minutes,
        command_token=secrets.token_urlsafe(32), state='reserved', kind='owner_credit' if owner_credit else 'wallet',
        deadline=deadline, created_at=now)
    db.session.add(session)
    try:
        hold_slots(session, slots)
    except ValueError as error:
        raise CafeError(str(error), 409)
    if owner_credit:
        return session
    w.reserved += price
    ledger(w, 'reserve', 0, {'id': f'gamer-{user_id}', 'name': 'Gamer self-service'},
           f'reserve:{session.id}', fp, session_id=session.id, reason='Awaiting PC acknowledgement')
    return session


def release_console(session):
    from app.services.cafe_slot_reservations import release_slots
    release_slots(session)
    session.console_claim = None
    db.session.flush()
    from sqlalchemy import text
    if db.engine.dialect.name == 'postgresql':
        db.session.execute(text(f'UPDATE VENDOR_{int(session.vendor_id)}_CONSOLE_AVAILABILITY SET is_available = true WHERE console_id = :cid'), {'cid': session.console_id})
    session.console_claim = None


def acknowledge(session_id, link, command_token, success):
    initial = db.session.get(CafePlaySession, session_id)
    if not initial or initial.link_id != link.id or not secrets.compare_digest(initial.command_token, str(command_token)):
        raise CafeError('Invalid PC acknowledgement', 403)
    w = wallet(initial.vendor_id, initial.user_id)
    session = CafePlaySession.query.filter_by(id=session_id).populate_existing().with_for_update().one()
    if session.state != 'reserved':
        return session
    if session.kind == 'existing_booking':
        from app.services.cafe_booking_service import acknowledge_booking
        return acknowledge_booking(session, link, success)
    if session.kind == 'owner_credit':
        if success and datetime.utcnow() < session.deadline:
            session.state = 'active'
            session.started_at = datetime.utcnow()
            session.ends_at = session.started_at + timedelta(minutes=session.minutes)
            session.due_amount = session.amount
            audit(session.vendor_id, {'id':f'pc-{link.console_id}','name':f'PC {link.console_id}'},
                  'credit_play.started', {'session_id':session.id,'amount':session.amount,'minutes':session.minutes})
        else:
            session.state = 'failed'
            release_console(session)
        return session
    actor = {'id': f'pc-{link.console_id}', 'name': f'PC {link.console_id}'}
    w.reserved -= session.amount
    if success and datetime.utcnow() < session.deadline:
        w.balance -= session.amount
        session.state = 'active'
        session.started_at = datetime.utcnow()
        session.ends_at = session.started_at + timedelta(minutes=session.minutes)
        ledger(w, 'capture', -session.amount, actor, f'capture:{session.id}', session.fingerprint,
               session_id=session.id, reason='PC acknowledged session start')
    else:
        session.state = 'failed'
        release_console(session)
        ledger(w, 'release', 0, actor, f'release:{session.id}', session.fingerprint,
               session_id=session.id, reason='PC failed to start or acknowledgement expired')
    return session


def expire_sessions():
    now = datetime.utcnow()
    changed = []
    # The reconciler can touch several cafes in one transaction. Lock their
    # financial serialization rows in vendor order before any session/request
    # locks, including warnings; this preserves endpoint lock order.
    from app.models.vendor import Vendor
    from app.models.cafe_wallet import CafeContinuation, CafeSlotReservation
    claims = db.session.query(CafeSlotReservation.session_id).filter(CafeSlotReservation.released_at.is_(None))
    vendor_ids = {r[0] for r in db.session.query(CafePlaySession.vendor_id).filter(
        (CafePlaySession.state.in_(['active','reserved'])) | CafePlaySession.id.in_(claims)).distinct().all()}
    vendor_ids.update(r[0] for r in db.session.query(CafeContinuation.vendor_id).filter_by(state='pending').distinct().all())
    if vendor_ids:
        Vendor.query.filter(Vendor.id.in_(vendor_ids)).order_by(Vendor.id).populate_existing().with_for_update().all()
    pending = CafePlaySession.query.filter(CafePlaySession.state == 'reserved', CafePlaySession.deadline <= now).all()
    from app.models.console_link_session import ConsoleLinkSession
    for session in pending:
        link = db.session.get(ConsoleLinkSession, session.link_id)
        if link:
            changed.append(acknowledge(session.id, link, session.command_token, False))
    from sqlalchemy import or_
    active = CafePlaySession.query.filter(CafePlaySession.state == 'active', or_(CafePlaySession.ends_at <= now, CafePlaySession.kind == 'existing_booking')).order_by(CafePlaySession.vendor_id, CafePlaySession.id).all()
    for initial in active:
        wallet(initial.vendor_id, initial.user_id)
        session = CafePlaySession.query.filter_by(id=initial.id).populate_existing().with_for_update().one()
        if session.state == 'active':
            if session.kind == 'existing_booking':
                from app.services.cafe_booking_service import reconcile_booking
                if not reconcile_booking(session):
                    continue
            else:
                # Funded duration ending starts overtime; staff explicitly release play.
                from app.services.cafe_slot_reservations import extend_overtime_slots
                extend_overtime_slots(session,now)
                changed.append(session)
                continue
            session.ended_at = now
            release_console(session)
            changed.append(session)
    # Migration backfills live sessions. Old code may finish one between the
    # migration and deployment, so recover its remaining claims once here too.
    from app.models.cafe_wallet import CafeSlotReservation
    unreleased = db.session.query(CafeSlotReservation.session_id).filter(CafeSlotReservation.released_at.is_(None))
    terminal = CafePlaySession.query.filter(CafePlaySession.id.in_(unreleased),
        CafePlaySession.state.in_(['failed','completed','cancelled','canceled'])).all()
    for initial in terminal:
        session = CafePlaySession.query.filter_by(id=initial.id).populate_existing().with_for_update().one()
        if session.state in ('failed','completed','cancelled','canceled'):
            release_console(session)
            changed.append(session)
    expired = CafeStaffSession.query.filter(CafeStaffSession.closed_at.is_(None), CafeStaffSession.expires_at <= now).all()
    for row in expired:
        row = CafeStaffSession.query.filter_by(jti=row.jti).populate_existing().with_for_update().one()
        if row.closed_at is None:
            row.closed_at = row.expires_at
            audit(row.vendor_id, {'id': row.actor_id, 'name': row.actor_name}, 'session.expired', {'jti': row.jti, 'expired_at': row.expires_at.isoformat()})
    from app.services.cafe_continuation_service import reconcile_notifications
    warnings = reconcile_notifications(now)
    db.session.commit()
    from app.services.cafe_continuation_service import publish_session
    for session in warnings:
        publish_session(session, 'session.warning' if session.state=='active' else None)
    from app.services.cafe_slot_reservations import notify_slot_changes
    for session in changed:
        notify_slot_changes(session)


def serialize(row):
    return {c.name: (getattr(row, c.name).isoformat() + 'Z' if isinstance(getattr(row, c.name), datetime)
                     else getattr(row, c.name)) for c in row.__table__.columns
            if c.name not in ('command_token', 'fingerprint', 'console_claim')}
