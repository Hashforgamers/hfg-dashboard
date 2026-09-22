from datetime import datetime
from functools import wraps
import os
import secrets
import uuid
import jwt
from flask import Blueprint, request, jsonify, current_app, g
from flask_jwt_extended import jwt_required, get_jwt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from app.extension.extensions import db
from app.models.cafe_wallet import *
from app.models.console_link_session import ConsoleLinkSession
from app.services.rbac_service import get_role_permissions
from app.services.cafe_wallet_service import (
    CafeError, policy, validate_policy, audit, wallet, topup, refund, reserve,
    acknowledge, expire_sessions, serialize, integer,
)

bp_cafe = Blueprint('cafe_wallet', __name__, url_prefix='/api/cafe')


@bp_cafe.errorhandler(CafeError)
def cafe_error(error):
    db.session.rollback()
    return jsonify(error=error.message), error.status


@bp_cafe.errorhandler(IntegrityError)
def conflict(error):
    db.session.rollback()
    return jsonify(error='Conflicting operation. Retry with the same idempotency key.'), 409


def staff_actor(vendor_id, permission):
    claims = get_jwt()
    actor = claims.get('staff') or {}
    if claims.get('scope') != 'vendor_access' or claims.get('vendor_id') != vendor_id or not actor.get('id'):
        raise CafeError('A named staff session for this cafe is required', 403)
    session = db.session.get(CafeStaffSession, claims.get('jti'))
    if not session or session.closed_at or session.expires_at <= datetime.utcnow():
        raise CafeError('Unlock your staff session again', 401)
    role = actor.get('role')
    if role != 'owner':
        from app.models.vendorStaff import VendorStaff
        member = VendorStaff.query.filter_by(id=actor['id'], vendor_id=vendor_id, is_active=True).first()
        if not member:
            raise CafeError('Staff account is disabled', 403)
        role = member.role
    if permission not in get_role_permissions(vendor_id).get(role, []):
        raise CafeError('Permission denied', 403)
    return {'id': str(actor['id']), 'name': str(actor['name'])}


def agent_link(token=None):
    token = token or request.headers.get('Authorization', '').removeprefix('Bearer ')
    if not token:
        raise CafeError('PC authentication required', 401)
    link = ConsoleLinkSession.query.filter_by(session_token=token, status='active').first()
    if not link:
        raise CafeError('PC authentication failed', 401)
    return link


def signer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='cafe-pc-qr-v1')


def resolve_qr(token):
    try:
        data = signer().loads(token, max_age=120)
    except (BadSignature, SignatureExpired, TypeError):
        raise CafeError('QR expired. Scan the current code on the PC.', 410)
    link = db.session.get(ConsoleLinkSession, data.get('link_id'))
    if not link or link.status != 'active':
        raise CafeError('PC is no longer linked', 410)
    return link


def gamer_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        token = request.headers.get('Authorization', '').removeprefix('Bearer ')
        try:
            claims = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'],
                                audience='cafe-checkout', options={'require': ['exp', 'iat', 'sub']})
            if claims.get('scope') != 'cafe_gamer':
                raise ValueError()
            g.cafe_user_id = int(claims['sub'])
        except (jwt.InvalidTokenError, ValueError, TypeError):
            raise CafeError('Sign in to Hash to continue', 401)
        return fn(*args, **kwargs)
    return wrapped


@bp_cafe.get('/<int:vendor_id>/policy')
@jwt_required()
def get_policy(vendor_id):
    staff_actor(vendor_id, 'wallet.topup')
    return jsonify(policy(vendor_id))


@bp_cafe.put('/<int:vendor_id>/policy')
@jwt_required()
def set_policy(vendor_id):
    actor = staff_actor(vendor_id, 'account.manage')
    settings = validate_policy(request.get_json(silent=True))
    from app.models.vendor import Vendor
    Vendor.query.filter_by(id=vendor_id).populate_existing().with_for_update().one()
    before = policy(vendor_id)
    if settings['self_service'] and db.engine.dialect.name == 'postgresql':
        from sqlalchemy import text
        db.session.execute(text('SELECT cafe_install_console_guards(:vid)'), {'vid': vendor_id})
    row = db.session.get(CafePaymentPolicy, vendor_id)
    if not row:
        row = CafePaymentPolicy(vendor_id=vendor_id)
        db.session.add(row)
    row.settings, row.updated_at = settings, datetime.utcnow()
    audit(vendor_id, actor, 'payment_policy.updated', {'before': before, 'after': settings})
    db.session.commit()
    return jsonify(settings)


@bp_cafe.get('/<int:vendor_id>/wallets/<int:user_id>')
@jwt_required()
def get_wallet(vendor_id, user_id):
    staff_actor(vendor_id, 'wallet.topup')
    row = CafeWallet.query.filter_by(vendor_id=vendor_id, user_id=user_id).first()
    entries = CafeLedger.query.filter_by(vendor_id=vendor_id, user_id=user_id).order_by(CafeLedger.id.desc()).limit(100).all()
    return jsonify(balance=row.balance if row else 0, reserved=row.reserved if row else 0,
                   ledger=[serialize(e) for e in entries])


@bp_cafe.post('/<int:vendor_id>/wallets/<int:user_id>/topups')
@jwt_required()
def desk_topup(vendor_id, user_id):
    actor = staff_actor(vendor_id, 'wallet.topup')
    entry = topup(vendor_id, user_id, request.get_json(silent=True) or {}, actor)
    db.session.commit()
    return jsonify(serialize(entry))


@bp_cafe.post('/<int:vendor_id>/ledger/<int:entry_id>/refund')
@jwt_required()
def refund_entry(vendor_id, entry_id):
    actor = staff_actor(vendor_id, 'wallet.refund')
    entry = refund(vendor_id, entry_id, request.get_json(silent=True) or {}, actor)
    db.session.commit()
    return jsonify(serialize(entry))


@bp_cafe.get('/<int:vendor_id>/shifts')
@jwt_required()
def shifts(vendor_id):
    actor = staff_actor(vendor_id, 'wallet.topup')
    rows = CafeShift.query.filter_by(vendor_id=vendor_id, actor_id=actor['id']).order_by(CafeShift.opened_at.desc()).limit(50).all()
    return jsonify([serialize(r) for r in rows])


@bp_cafe.post('/<int:vendor_id>/shifts/open')
@jwt_required()
def open_shift(vendor_id):
    actor = staff_actor(vendor_id, 'wallet.topup')
    from app.models.vendor import Vendor
    Vendor.query.filter_by(id=vendor_id).populate_existing().with_for_update().one()
    existing = CafeShift.query.filter_by(open_key=f"{vendor_id}:{actor['id']}").first()
    if existing:
        return jsonify(serialize(existing))
    amount = integer((request.get_json(silent=True) or {}).get('opening_cash'), 0)
    row = CafeShift(id=str(uuid.uuid4()), vendor_id=vendor_id, actor_id=actor['id'],
                    actor_name=actor['name'], open_key=f"{vendor_id}:{actor['id']}", opening_cash=amount)
    db.session.add(row)
    audit(vendor_id, actor, 'shift.opened', {'shift_id': row.id, 'opening_cash': amount})
    db.session.commit()
    return jsonify(serialize(row))


@bp_cafe.post('/<int:vendor_id>/shifts/<shift_id>/close')
@jwt_required()
def close_shift(vendor_id, shift_id):
    actor = staff_actor(vendor_id, 'wallet.topup')
    from app.models.vendor import Vendor
    Vendor.query.filter_by(id=vendor_id).populate_existing().with_for_update().one()
    row = CafeShift.query.filter_by(id=shift_id, vendor_id=vendor_id, actor_id=actor['id']).populate_existing().with_for_update().first()
    if not row:
        raise CafeError('Shift not found', 404)
    if row.closed_at:
        return jsonify(serialize(row))
    counted = integer((request.get_json(silent=True) or {}).get('counted_cash'), 0)
    def collected(method):
        return int(db.session.query(func.coalesce(func.sum(CafeLedger.amount), 0)).filter_by(shift_id=shift_id, method=method).scalar())
    row.expected_cash = row.opening_cash + collected('cash')
    row.upi_receipts = collected('cafe_upi')
    row.counted_cash, row.closed_at, row.open_key = counted, datetime.utcnow(), None
    audit(vendor_id, actor, 'shift.closed', {'shift_id': row.id, 'expected_cash': row.expected_cash,
          'counted_cash': counted, 'discrepancy': counted - row.expected_cash, 'upi_receipts': row.upi_receipts})
    db.session.commit()
    return jsonify(serialize(row))


@bp_cafe.get('/<int:vendor_id>/audit')
@jwt_required()
def audit_history(vendor_id):
    staff_actor(vendor_id, 'transactions.view')
    before = request.args.get('before', type=int)
    query = CafeAudit.query.filter_by(vendor_id=vendor_id)
    if before:
        query = query.filter(CafeAudit.id < before)
    return jsonify([serialize(r) for r in query.order_by(CafeAudit.id.desc()).limit(100).all()])


@bp_cafe.get('/<int:vendor_id>/report')
@jwt_required()
def money_report(vendor_id):
    staff_actor(vendor_id, 'transactions.view')
    totals = db.session.query(CafeLedger.kind, func.sum(CafeLedger.amount)).filter_by(vendor_id=vendor_id).group_by(CafeLedger.kind).all()
    return jsonify(totals={kind:int(amount) for kind,amount in totals}, sessions=[serialize(r) for r in CafePlaySession.query.filter_by(vendor_id=vendor_id).order_by(CafePlaySession.created_at.desc()).limit(100).all()])


@bp_cafe.post('/<int:vendor_id>/logout')
@jwt_required()
def logout(vendor_id):
    actor = staff_actor(vendor_id, 'dashboard.view')
    row = CafeStaffSession.query.filter_by(jti=get_jwt()['jti']).populate_existing().with_for_update().one()
    row.closed_at = datetime.utcnow()
    audit(vendor_id, actor, 'session.logout', {'jti': row.jti})
    db.session.commit()
    return jsonify(ok=True)


@bp_cafe.post('/agent/qr')
def agent_qr():
    link = agent_link()
    from urllib.parse import urlencode
    token = signer().dumps({'link_id': link.id})
    base = current_app.config.get('CAFE_CHECKOUT_URL')
    if not base:
        raise CafeError('Cafe checkout URL has not been configured', 503)
    return jsonify(token=token, checkout_url=base + '?' + urlencode({'qr': token}), expires_in=120,
                   console_id=link.console_id, vendor_id=link.vendor_id)


def checkout_details(link, user_id, include_bookings=False):
    from app.models.vendor import Vendor
    from app.models.console import Console
    row = CafeWallet.query.filter_by(vendor_id=link.vendor_id, user_id=user_id).first()
    result = dict(cafe_name=db.session.get(Vendor, link.vendor_id).cafe_name,
        console_number=db.session.get(Console, link.console_id).console_number,
        vendor_id=link.vendor_id, console_id=link.console_id, policy=policy(link.vendor_id),
        available_balance=(row.balance-row.reserved) if row else 0)
    if include_bookings:
        from app.services.cafe_booking_service import existing_bookings
        result['bookings'] = existing_bookings(link, user_id)
        active = CafePlaySession.query.filter_by(link_id=link.id, user_id=user_id).filter(CafePlaySession.state.in_(['reserved','active'])).first()
        result['active_session_id'] = active.id if active else None
    return result


def public_session(row):
    link = db.session.get(ConsoleLinkSession, row.link_id)
    return dict(serialize(row), checkout=checkout_details(link, row.user_id))


@bp_cafe.get('/checkout')
@gamer_required
def checkout_info():
    link = resolve_qr(request.args.get('qr'))
    return jsonify(checkout_details(link, g.cafe_user_id, include_bookings=True))


@bp_cafe.post('/checkout')
@gamer_required
def checkout():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or body.get('meals'):
        raise CafeError('Food orders have a separate checkout.')
    link = resolve_qr(body.get('qr'))
    if body.get('booking_id') is not None:
        if body.get('payment_method') not in (None, 'existing_booking'):
            raise CafeError('Existing bookings do not require a second payment.')
        from app.services.cafe_booking_service import reserve_booking
        session = reserve_booking(link, g.cafe_user_id, body['booking_id'], body.get('idempotency_key'))
    else:
        if body.get('payment_method') != 'cafe_wallet':
            raise CafeError('Select cafe wallet.')
        session = reserve(link.vendor_id, g.cafe_user_id, link, body.get('minutes'), body.get('idempotency_key'),
                          expected_amount=integer(body.get('expected_amount')))
    db.session.commit()
    if session.state == 'reserved':
        from app.services.websocket_service import socketio
        socketio.emit('session.prepare', command(session), to=f'cafe-agent:{link.id}', namespace='/cafe-agent')
    return jsonify(public_session(session)), 202 if session.state == 'reserved' else 200


def command(session):
    return dict(serialize(session), command_token=session.command_token)


@bp_cafe.get('/sessions/<session_id>')
@gamer_required
def session_status(session_id):
    row = CafePlaySession.query.filter_by(id=session_id, user_id=g.cafe_user_id).first()
    if not row:
        raise CafeError('Session not found', 404)
    return jsonify(public_session(row))


@bp_cafe.get('/agent/session')
def agent_session():
    link = agent_link()
    row = CafePlaySession.query.filter_by(link_id=link.id).filter(CafePlaySession.state.in_(['reserved', 'active'])).first()
    return jsonify(command(row) if row else None)


@bp_cafe.post('/agent/ack')
def agent_ack():
    link = agent_link()
    body = request.get_json(silent=True) or {}
    if type(body.get('success')) is not bool:
        raise CafeError('success must be boolean')
    row = acknowledge(body.get('session_id'), link, body.get('command_token'), body['success'])
    db.session.commit()
    return jsonify(serialize(row))


def register_cafe_runtime(app, socketio):
    app.register_error_handler(CafeError, cafe_error)
    from flask_socketio import join_room
    @socketio.on('connect', namespace='/cafe-agent')
    def connect(auth):
        try:
            link = agent_link((auth or {}).get('token'))
            join_room(f'cafe-agent:{link.id}')
        except CafeError:
            return False

    @app.cli.command('cafe-reconcile')
    def reconcile():
        """Expire reservations, complete sessions and record staff session expiry."""
        expire_sessions()

    def worker():
        while True:
            with app.app_context():
                try:
                    expire_sessions()
                except Exception:
                    db.session.rollback()
                    app.logger.exception('Cafe reconciliation failed')
                finally:
                    db.session.remove()
            socketio.sleep(5)
    if app.config.get('CAFE_RECONCILER_ENABLED', False):
        socketio.start_background_task(worker)


@bp_cafe.get('/food/menu')
@gamer_required
def food_menu():
    from app.models.extraServiceMenu import ExtraServiceMenu
    from app.models.extraServiceCategory import ExtraServiceCategory
    link = food_context(request.args)
    settings = policy(link.vendor_id)
    if not settings['food_ordering']:
        raise CafeError('Food ordering is disabled', 403)
    rows = db.session.query(ExtraServiceMenu).join(ExtraServiceCategory).filter(
        ExtraServiceCategory.vendor_id == link.vendor_id, ExtraServiceCategory.is_active.is_(True),
        ExtraServiceMenu.is_active.is_(True)).all()
    from decimal import Decimal, ROUND_HALF_UP
    return jsonify(collector=settings['food_collection'], items=[{'id':r.id,'name':r.name,
        'amount':int((Decimal(str(r.price))*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)),
        'stock':r.stock_quantity} for r in rows])


@bp_cafe.post('/food/orders')
@gamer_required
def food_order():
    from decimal import Decimal, ROUND_HALF_UP
    from app.models.extraServiceMenu import ExtraServiceMenu
    from app.models.extraServiceCategory import ExtraServiceCategory
    from app.services.cafe_wallet_service import fingerprint, key
    from app.models.vendor import Vendor
    body = request.get_json(silent=True) or {}
    link = food_context(body)
    Vendor.query.filter_by(id=link.vendor_id).populate_existing().with_for_update().one()
    settings = policy(link.vendor_id)
    if not settings['food_ordering']:
        raise CafeError('Food ordering is disabled', 403)
    selections = body.get('items')
    if not isinstance(selections, list) or not 1 <= len(selections) <= 30:
        raise CafeError('Select 1–30 food items')
    idem = key(body.get('idempotency_key'))
    fp = fingerprint(selections)
    existing = CafeFoodOrder.query.filter_by(vendor_id=link.vendor_id, user_id=g.cafe_user_id, idempotency_key=idem).first()
    if existing:
        if existing.fingerprint != fp:
            raise CafeError('Idempotency key already used', 409)
        return jsonify(serialize(existing))
    items, total, seen = [], 0, set()
    for selected in selections:
        if not isinstance(selected, dict):
            raise CafeError('Invalid food item')
        menu_id, quantity = integer(selected.get('id')), integer(selected.get('quantity'), 1, 50)
        if menu_id in seen:
            raise CafeError('Duplicate food item')
        seen.add(menu_id)
        menu = db.session.query(ExtraServiceMenu).join(ExtraServiceCategory).filter(
            ExtraServiceMenu.id == menu_id, ExtraServiceCategory.vendor_id == link.vendor_id,
            ExtraServiceCategory.is_active.is_(True), ExtraServiceMenu.is_active.is_(True)
        ).with_for_update(of=ExtraServiceMenu).first()
        if not menu or (menu.stock_quantity is not None and menu.stock_quantity < quantity):
            raise CafeError('Food item unavailable', 409)
        unit = int((Decimal(str(menu.price))*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        if unit < 0:
            raise CafeError('Invalid menu price')
        if menu.stock_quantity is not None:
            menu.stock_quantity -= quantity
        items.append({'id': menu.id, 'name': menu.name, 'quantity': quantity, 'unit_amount': unit})
        total += unit * quantity
    order = CafeFoodOrder(id=str(uuid.uuid4()), vendor_id=link.vendor_id, user_id=g.cafe_user_id,
        items=items, amount=total, collector=settings['food_collection'], state='pay_at_store',
        idempotency_key=idem, fingerprint=fp)
    db.session.add(order)
    audit(link.vendor_id, {'id':f'gamer-{g.cafe_user_id}', 'name':'Gamer self-service'},
          'food.ordered', {'order_id':order.id,'collector':order.collector,'amount':total})
    db.session.commit()
    return jsonify(serialize(order)), 201


@bp_cafe.get('/<int:vendor_id>/food/orders')
@jwt_required()
def desk_food_orders(vendor_id):
    staff_actor(vendor_id, 'store.manage')
    return jsonify([serialize(o) for o in CafeFoodOrder.query.filter_by(vendor_id=vendor_id).order_by(CafeFoodOrder.created_at.desc()).limit(100).all()])


@bp_cafe.post('/<int:vendor_id>/food/orders/<order_id>/collect')
@jwt_required()
def collect_food(vendor_id, order_id):
    actor = staff_actor(vendor_id, 'wallet.topup')
    body = request.get_json(silent=True) or {}
    order = CafeFoodOrder.query.filter_by(id=order_id, vendor_id=vendor_id).first()
    if not order:
        raise CafeError('Order not found', 404)
    if order.collector != 'cafe':
        raise CafeError('The food store collects this order directly', 403)
    from app.services.cafe_wallet_service import ledger, fingerprint
    w = wallet(vendor_id, order.user_id)
    order = CafeFoodOrder.query.filter_by(id=order_id).populate_existing().with_for_update().one()
    if order.state == 'paid':
        return jsonify(serialize(order))
    method = body.get('method')
    if method not in policy(vendor_id)['desk_methods']:
        raise CafeError('Desk payment method disabled', 403)
    shift = CafeShift.query.filter_by(open_key=f"{vendor_id}:{actor['id']}").first()
    if not shift:
        raise CafeError('Open your shift before collecting payment', 409)
    # Collection enters shift reconciliation, never the gamer's wallet balance.
    ledger(w, 'food_collection', order.amount, actor, f'food:{order.id}', fingerprint([order.id]),
           method=method, shift_id=shift.id, reason=f'Food order {order.id}')
    order.state = 'paid'
    audit(vendor_id, actor, 'food.collected', {'order_id':order.id, 'method':method, 'amount':order.amount})
    db.session.commit()
    return jsonify(serialize(order))


@bp_cafe.post('/<int:vendor_id>/wallets/<int:user_id>/adjustments')
@jwt_required()
def adjust_wallet(vendor_id, user_id):
    from app.services.cafe_wallet_service import key, fingerprint, ledger
    actor = staff_actor(vendor_id, 'wallet.adjust')
    body = request.get_json(silent=True) or {}
    amount = integer(body.get('amount'), -100000000, 100000000)
    reason = str(body.get('reason') or '').strip()
    if not amount or not 3 <= len(reason) <= 500:
        raise CafeError('A nonzero amount and adjustment reason are required')
    idem = key(body.get('idempotency_key'))
    fp = fingerprint([user_id, amount, reason])
    w = wallet(vendor_id, user_id)
    from app.models.user import User
    if not db.session.get(User,user_id):
        raise CafeError('Gamer not found', 404)
    existing = CafeLedger.query.filter_by(vendor_id=vendor_id,idempotency_key=idem).first()
    if existing:
        if existing.fingerprint != fp or existing.actor_id != actor['id']:
            raise CafeError('Idempotency key already used', 409)
        return jsonify(serialize(existing))
    if w.balance + amount < w.reserved:
        raise CafeError('Adjustment would spend reserved funds', 409)
    w.balance += amount
    entry = ledger(w, 'adjustment', amount, actor, idem, fp, reason=reason)
    audit(vendor_id, actor, 'wallet.adjusted', {'user_id':user_id, 'amount':amount, 'reason':reason})
    db.session.commit()
    return jsonify(serialize(entry))


def food_context(data):
    session_id = data.get('session_id')
    if session_id:
        row = CafePlaySession.query.filter_by(id=session_id, user_id=g.cafe_user_id).first()
        if not row or row.state not in ('reserved', 'active'):
            raise CafeError('An active session is required', 403)
        return db.session.get(ConsoleLinkSession, row.link_id)
    return resolve_qr(data.get('qr'))
