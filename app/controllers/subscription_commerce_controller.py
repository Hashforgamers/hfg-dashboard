import hashlib
import hmac
import os
from html import escape
from flask import Blueprint, request, jsonify, current_app, Response
from app.extension.extensions import db
from app.models.subscription_checkout import SubscriptionCheckout
from app.services import subscription_commerce as commerce
from app.services import razorpay_service as gateway
from app.services.kiosk_security import vendor_identity, bearer_token, KioskError

bp_commerce=Blueprint('subscription_commerce',__name__)

@bp_commerce.before_request
def authorize():
    if request.method=='OPTIONS' or request.endpoint=='subscription_commerce.webhook': return
    try:
        identity=vendor_identity(bearer_token(),'subscription.manage')
        if identity['vendor_id']!=request.view_args.get('vendor_id'): raise KioskError('vendor_mismatch',403)
    except KioskError as error:
        return jsonify(error=error.error_code),error.code

@bp_commerce.errorhandler(ValueError)
def invalid(error):
    db.session.rollback()
    return jsonify(error=str(error)),400


def owned(vendor_id,checkout_id):
    row=SubscriptionCheckout.query.filter_by(id=checkout_id,vendor_id=vendor_id).populate_existing().first()
    if not row: raise ValueError('Purchase not found')
    return row

@bp_commerce.post('/api/vendors/<int:vendor_id>/subscription/preview')
def preview(vendor_id):
    return jsonify(commerce.public_quote(commerce.preview(vendor_id,request.get_json(silent=True)))),201

@bp_commerce.get('/api/vendors/<int:vendor_id>/subscription/purchases')
def purchases(vendor_id):
    rows=SubscriptionCheckout.query.filter_by(vendor_id=vendor_id).filter(SubscriptionCheckout.state.in_(['paid','paid_unapplied','ordered'])).order_by(SubscriptionCheckout.created_at.desc()).limit(100).all()
    return jsonify(purchases=[commerce.public_quote(row) for row in rows])

@bp_commerce.post('/api/vendors/<int:vendor_id>/subscription/purchases/<checkout_id>/pay')
def pay(vendor_id,checkout_id):
    commerce.lock_vendor(vendor_id);row=owned(vendor_id,checkout_id)
    if row.state in {'paid','paid_unapplied'}: return jsonify(commerce.public_quote(row))
    if row.order_id:
        return jsonify(**commerce.public_quote(row),key_id=current_app.config['RAZORPAY_KEY_ID'])
    if commerce._as_utc(row.expires_at)<=commerce.utcnow(): raise ValueError('Preview expired; review a fresh preview')
    commerce.check_base(row)
    # Do not create concurrent payable orders for conflicting subscription changes.
    pending=SubscriptionCheckout.query.filter_by(vendor_id=vendor_id,state='ordered').filter(SubscriptionCheckout.id!=row.id).first()
    if pending: raise ValueError('A payment is pending. Resume or reconcile it before starting another purchase.')
    if row.snapshot['amount_paise']==0:
        return jsonify(commerce.public_quote(commerce.activate(row)))
    order=gateway.create_order(amount=row.snapshot['amount_paise']/100,currency='INR',receipt=row.id,
        notes={'purpose':'subscription_checkout','checkout_id':row.id,'vendor_id':str(vendor_id)})
    row.order_id=order['id'];row.state='ordered';db.session.commit()
    return jsonify(**commerce.public_quote(row),key_id=current_app.config['RAZORPAY_KEY_ID'])

@bp_commerce.post('/api/vendors/<int:vendor_id>/subscription/purchases/<checkout_id>/reconcile')
def reconcile(vendor_id,checkout_id):
    commerce.lock_vendor(vendor_id);row=owned(vendor_id,checkout_id)
    if row.state in {'paid','paid_unapplied'}: return jsonify(commerce.public_quote(row))
    if not row.order_id: raise ValueError('No payment order exists')
    payments=gateway.get_order_payments(row.order_id)
    for payment in payments:
        if payment.get('status')=='captured': return jsonify(commerce.public_quote(commerce.activate(row,payment)))
    db.session.rollback()
    return jsonify(commerce.public_quote(row))

@bp_commerce.post('/api/subscription-payments/webhook')
def webhook():
    secret=current_app.config.get('SUBSCRIPTION_WEBHOOK_SECRET') or os.getenv('SUBSCRIPTION_WEBHOOK_SECRET')
    if not secret: return jsonify(error='Webhook is not configured'),503
    signature=request.headers.get('X-Razorpay-Signature','')
    expected=hmac.new(secret.encode(),request.get_data(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature,expected): return jsonify(error='Invalid signature'),401
    data=request.get_json(silent=True) or {}
    if data.get('event') not in {'payment.captured','order.paid'}: return jsonify(ok=True)
    entity=((data.get('payload') or {}).get('payment') or {}).get('entity') or {}
    row=SubscriptionCheckout.query.filter_by(order_id=entity.get('order_id')).first() if entity.get('order_id') else None
    if not row: return jsonify(ok=True)
    commerce.lock_vendor(row.vendor_id)
    row=owned(row.vendor_id,row.id)
    if row.state not in {'paid','paid_unapplied'}: commerce.activate(row,gateway.get_payment_details(entity['id']))
    return jsonify(ok=True)

@bp_commerce.get('/api/vendors/<int:vendor_id>/subscription/purchases/<checkout_id>/invoice')
def invoice(vendor_id,checkout_id):
    row=owned(vendor_id,checkout_id);data=commerce.public_quote(row);paid=row.paid_at is not None
    title='Payment invoice' if paid else 'Invoice preview — unpaid'
    if row.state=='paid_unapplied': title='Payment receipt — activation needs support'
    snapshot=row.snapshot;terms=snapshot['terms']
    fields={'Reference':data['invoice_number'] or row.id,'Cafe':snapshot['customer']['cafe_name'],
            'Plan':terms['package_name'],'PC / kiosk limit':terms['pc_limit'],'Billing cycle':terms['billing_cycle'],
            'Period start':snapshot['period_start'],'Period end':snapshot['period_end'],
            'Payment reference':row.payment_id or ('No payment required' if paid else 'Not paid'),
            'Details':snapshot.get('activation_error') or snapshot['description'],'Total (INR)':f"{snapshot['amount_paise']/100:.2f}"}
    lines=''.join(f'<tr><th>{escape(str(k))}</th><td>{escape(str(v))}</td></tr>' for k,v in fields.items())
    html=f'''<!doctype html><html><head><meta charset="utf-8"><title>{escape(title)}</title>
    <style>body{{font:16px Arial;margin:40px;color:#172033}}table{{border-collapse:collapse;width:100%;max-width:800px}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #ddd}}@media print{{button{{display:none}}}}</style></head>
    <body><h1>Hash For Gamers</h1><h2>{escape(title)}</h2><table>{lines}</table>
    <p>{escape(snapshot['tax_note'])}</p><p>{'Payment received.' if paid else 'Preview only. This is not proof of payment.'}</p></body></html>'''
    return Response(html,mimetype='text/html',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
