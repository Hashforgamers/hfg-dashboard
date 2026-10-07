"""New kiosk protocol; legacy clients remain on their existing endpoints."""
from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended import jwt_required, get_jwt
from app.extension.extensions import db
from app.models.session_extension import RuntimeSession, ExtensionQuote, SessionNotice, SessionExtensionPolicy
from app.services import session_extensions as service
from app.services.cafe_wallet_service import CafeError, integer
from app.controllers.cafe_wallet_controller import agent_link, staff_actor

bp_extensions=Blueprint('session_extensions',__name__)

@bp_extensions.after_request
def private_session_response(response):
    response.headers['Cache-Control']='private, no-store'
    response.vary.add('Authorization')
    return response


@bp_extensions.errorhandler(IntegrityError)
def conflicting_mutation(exc):
    db.session.rollback()
    return jsonify(error='Conflicting mutation; retry with the same idempotency key.'),409

def check_ready():
    if not service.ready(): raise CafeError('Session extension migration is required',503)

def body():
    data=request.get_json(silent=True)
    if not isinstance(data,dict): raise CafeError('Supply a JSON object')
    return data

def device_row(data):
    check_ready();link=agent_link()
    row=service.lock_row(data.get('runtime_id'),link_id=link.id)
    if row.ended_at and RuntimeSession.query.filter(RuntimeSession.link_id==link.id,RuntimeSession.ended_at.is_(None),RuntimeSession.id!=row.id).first():
        raise CafeError('Kiosk has moved to another session',409)
    service.seen(row)
    return row

def answer(row,status=200):
    result=service.snapshot(row);db.session.commit();service.dispatch()
    return jsonify(result),status

@bp_extensions.get('/api/kiosk/session')
def current_session():
    check_ready();link=agent_link()
    row=RuntimeSession.query.filter_by(link_id=link.id,ended_at=None).order_by(RuntimeSession.started_at.desc()).first()
    if not row:
        return jsonify(session=None,capabilities=['session_extensions_v1'],server_time=service.stamp(service.datetime.utcnow()))
    service.seen(row)
    result=service.snapshot(row);db.session.commit();service.dispatch()
    return jsonify(session=result,capabilities=['session_extensions_v1'])

@bp_extensions.post('/api/kiosk/session/extension/quote')
def extension_quote():
    check_ready();data=body();link=agent_link()
    row=service.lock_row(data['runtime_id'],link_id=link.id) if data.get('runtime_id') else service.attach(link,data.get('session_ref'))
    service.seen(row)
    q,result=service.quote(row);result['runtime_id']=row.id;db.session.commit();service.dispatch()
    return jsonify(result)

@bp_extensions.post('/api/kiosk/session/continue')
def device_continue():
    data=body();row=device_row(data)
    q=service.continue_session(row,data.get('quote_id'),data)
    return answer(row,200 if q.status=='granted' else 202)

@bp_extensions.post('/api/kiosk/session/stop')
def device_stop():
    data=body();row=device_row(data)
    service.stop(row,data)
    return answer(row)

@bp_extensions.get('/api/cafe/<int:vendor_id>/extensions')
@jwt_required()
def staff_sessions(vendor_id):
    check_ready();staff_actor(vendor_id,'dashboard.view')
    rows=RuntimeSession.query.filter_by(vendor_id=vendor_id).filter((RuntimeSession.ended_at.is_(None)) | (RuntimeSession.status=='ended_unsettled')).order_by(RuntimeSession.started_at.desc()).limit(100).all()
    from app.models.user import User
    from app.models.console import Console
    items=[]
    for row in rows:
        snap=service.snapshot(row);user=db.session.get(User,row.user_id);console=db.session.get(Console,row.console_id)
        snap.update(gamer_name=getattr(user,'name',None) or 'Guest',console_name=getattr(console,'console_name',None) or f'PC {row.console_id}')
        pending=ExtensionQuote.query.filter(ExtensionQuote.runtime_id==row.id,ExtensionQuote.status.in_(['approval_pending','conflict_pending'])).order_by(ExtensionQuote.starts_at.desc()).first()
        snap['request_id']=pending.id if pending else None;items.append(snap)
    notices=SessionNotice.query.filter_by(vendor_id=vendor_id,read_at=None).order_by(SessionNotice.created_at.desc()).limit(100).all()
    return jsonify(items=items,notices=[{'id':n.id,'runtime_id':n.runtime_id,'kind':n.kind,'details':n.details,'created_at':service.stamp(n.created_at)} for n in notices])

@bp_extensions.post('/api/cafe/<int:vendor_id>/extensions/<runtime_id>/decision')
@jwt_required()
def decision(vendor_id,runtime_id):
    check_ready();actor=staff_actor(vendor_id,'booking.manage');data=body()
    row=service.lock_row(runtime_id,vendor_id=vendor_id)
    q=ExtensionQuote.query.filter_by(id=data.get('request_id'),runtime_id=row.id).with_for_update().first()
    if not q: raise CafeError('Request not found',404)
    if (q.status=='approval_pending' or data.get('decision')=='approve') and (get_jwt().get('staff') or {}).get('role')!='owner':
        raise CafeError('Only owner can authorize credit',403)
    service.decide(row,q,data,actor)
    return answer(row)

@bp_extensions.post('/api/cafe/<int:vendor_id>/extensions/<runtime_id>/end')
@jwt_required()
def staff_end(vendor_id,runtime_id):
    check_ready();staff_actor(vendor_id,'booking.manage');row=service.lock_row(runtime_id,vendor_id=vendor_id)
    service.stop(row,body());return answer(row)

@bp_extensions.post('/api/cafe/<int:vendor_id>/extensions/<runtime_id>/settle')
@jwt_required()
def settlement(vendor_id,runtime_id):
    check_ready();actor=staff_actor(vendor_id,'wallet.topup');row=service.lock_row(runtime_id,vendor_id=vendor_id)
    data=body()
    if data.get('method')=='waiver': staff_actor(vendor_id,'wallet.adjust')
    service.receipt(row,data,actor);return answer(row)

@bp_extensions.get('/api/cafe/<int:vendor_id>/extension-policy')
@jwt_required()
def read_policy(vendor_id):
    check_ready();staff_actor(vendor_id,'dashboard.view');return jsonify(service.settings(vendor_id))

@bp_extensions.put('/api/cafe/<int:vendor_id>/extension-policy')
@jwt_required()
def update_policy(vendor_id):
    check_ready();actor=staff_actor(vendor_id,'account.manage')
    if (get_jwt().get('staff') or {}).get('role')!='owner': raise CafeError('Only owner can change credit policy',403)
    data=body();mode=data.get('self_qr_credit_mode');limit=data.get('credit_limit_paise')
    if mode not in ('automatic','owner_approval'): raise CafeError('Choose automatic or owner_approval')
    if limit is not None: integer(limit,0)
    from app.services.cafe_wallet_service import wallet, audit
    from app.models.vendor import Vendor
    Vendor.query.filter_by(id=vendor_id).with_for_update().one()
    row=db.session.get(SessionExtensionPolicy,vendor_id)
    if not row: row=SessionExtensionPolicy(vendor_id=vendor_id);db.session.add(row)
    row.credit_mode=mode;row.credit_limit=limit;row.updated_at=service.datetime.utcnow()
    audit(vendor_id,actor,'extension.policy_changed',data);db.session.commit()
    return jsonify(service.settings(vendor_id))

@bp_extensions.post('/api/cafe/<int:vendor_id>/extension-notices/<notice_id>/read')
@jwt_required()
def read_notice(vendor_id,notice_id):
    check_ready();staff_actor(vendor_id,'dashboard.view')
    row=SessionNotice.query.filter_by(id=notice_id,vendor_id=vendor_id).with_for_update().first()
    if not row: raise CafeError('Notice not found',404)
    row.read_at=service.datetime.utcnow();db.session.commit();return jsonify(success=True)


@bp_extensions.get('/api/cafe/extensions/<runtime_id>')
def gamer_extension_snapshot(runtime_id):
    from app.controllers.cafe_wallet_controller import gamer_required
    from flask import g
    @gamer_required
    def read():
        check_ready();row=RuntimeSession.query.filter_by(id=runtime_id,user_id=g.cafe_user_id).first()
        if not row: raise CafeError('Session not found',404)
        return jsonify(service.snapshot(row))
    return read()


@bp_extensions.get('/api/cafe/<int:vendor_id>/extensions/<runtime_id>')
@jwt_required()
def staff_snapshot(vendor_id,runtime_id):
    check_ready();staff_actor(vendor_id,'dashboard.view')
    row=RuntimeSession.query.filter_by(id=runtime_id,vendor_id=vendor_id).first()
    if not row: raise CafeError('Session not found',404)
    return jsonify(service.snapshot(row))
