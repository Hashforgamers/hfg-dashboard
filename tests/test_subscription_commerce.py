"""Real routes/models; only payment-provider calls and clock are substituted."""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
import hashlib,hmac,json
import pytest
from test_subscription_checkout import app,auth,db,Package,Subscription,Console
from app.controllers import subscription_commerce_controller as routes
from app.controllers.package_controller import bp_packages
from app.models.subscription_checkout import SubscriptionCheckout
from app.models.vendor import Vendor
from app.models.console_link_session import ConsoleLinkSession
from app.services import subscription_commerce as service
from app.services.subscription_service import get_vendor_pc_limit

@pytest.fixture
def commerce(app,monkeypatch):
    app.register_blueprint(routes.bp_commerce)
    app.register_blueprint(bp_packages,url_prefix='/api/packages')
    app.config['SUBSCRIPTION_WEBHOOK_SECRET']='local-webhook-secret'
    db.metadata.create_all(db.engine,tables=[Vendor.__table__,Console.__table__,ConsoleLinkSession.__table__,SubscriptionCheckout.__table__])
    base=Package.query.filter_by(code='base').one();base.features={'price_inr':100,'extra_pc_monthly':20,'entitlements':['kiosk','pricing']}
    db.session.add(Package(code='pro',name='Pro',pc_limit=10,features={'price_inr':200,'extra_pc_monthly':20,'entitlements':['kiosk','pricing','staff']},active=True));db.session.commit()
    monkeypatch.setattr(routes.gateway,'create_order',Mock(return_value={'id':'order_new'}))
    monkeypatch.setattr(routes.gateway,'get_order_payments',Mock(return_value=[]))
    monkeypatch.setattr(routes.gateway,'get_payment_details',Mock())
    yield app
    db.session.remove()
    if db.engine.dialect.name != "postgresql":
        db.metadata.drop_all(db.engine,tables=[SubscriptionCheckout.__table__,ConsoleLinkSession.__table__,Console.__table__])


def preview(app,code='base',extra=0,cycle='monthly'):
    result=app.test_client().post('/api/vendors/1/subscription/preview',headers=auth(app),json={'package_code':code,'extra_pcs':extra,'billing_cycle':cycle})
    assert result.status_code==201,result.json
    return result.json


def pay(app,quote):
    return app.test_client().post(f'/api/vendors/1/subscription/purchases/{quote["id"]}/pay',headers=auth(app))


def captured(app,quote):
    return dict(id='pay_'+quote['id'],order_id='order_new',amount=quote['amount_paise'],currency='INR',status='captured')


def finish(app,quote):
    routes.gateway.get_order_payments.return_value=[captured(app,quote)]
    response=app.test_client().post(f'/api/vendors/1/subscription/purchases/{quote["id"]}/reconcile',headers=auth(app))
    assert response.status_code==200,response.json
    return response.json


def test_purchase_snapshot_invoice_and_idempotency(commerce):
    a=commerce;q=preview(a);assert q['amount_paise']==10000
    before=a.test_client().get(f'/api/vendors/1/subscription/purchases/{q["id"]}/invoice',headers=auth(a))
    assert b'Preview only' in before.data and b'&lt;Cafe&gt;' in before.data
    assert pay(a,q).status_code==200
    assert pay(a,q).status_code==200
    routes.gateway.create_order.assert_called_once()
    package=Package.query.filter_by(code='base').one();package.name='Edited later';package.pc_limit=99;package.features={'price_inr':999};db.session.commit()
    paid=finish(a,q);assert paid['state']=='paid' and paid['terms']['pc_limit']==5
    assert get_vendor_pc_limit(1)==5
    current=a.test_client().get('/api/vendors/1/subscription/',headers=auth(a))
    assert current.status_code==200,current.json
    assert current.json['pc_limit']==5 and current.json['commercial_terms']['package_name']=='Base'
    assert current.json['active_links']==0
    assert finish(a,q)['invoice_number']==paid['invoice_number'] and Subscription.query.count()==1
    after=a.test_client().get(f'/api/vendors/1/subscription/purchases/{q["id"]}/invoice',headers=auth(a))
    assert b'Payment received.' in after.data and b'Edited later' not in after.data


def test_prorated_upgrade_keeps_renewal_date(commerce,monkeypatch):
    a=commerce;q=preview(a);pay(a,q);finish(a,q)
    sub=Subscription.query.one();start=service._as_utc(sub.current_period_start);end=service._as_utc(sub.current_period_end)
    monkeypatch.setattr(service,'utcnow',lambda:start+(end-start)/2)
    # Current subscription lookup uses the real clock; it remains valid at both instants.
    upgraded=preview(a,'pro',extra=2)
    assert upgraded['amount_paise']==7000
    assert datetime.fromisoformat(upgraded['period_end'])==end
    routes.gateway.create_order.return_value={'id':'order_upgrade'}
    pay(a,upgraded);payment=captured(a,upgraded);payment['order_id']='order_upgrade'
    routes.gateway.get_order_payments.return_value=[payment]
    response=a.test_client().post(f'/api/vendors/1/subscription/purchases/{upgraded["id"]}/reconcile',headers=auth(a))
    assert response.status_code==200,response.json
    active=service.get_active_subscription(1,ts=service.utcnow())
    assert service.terms(active)['pc_limit']==12
    assert service._as_utc(active.current_period_end)==end


def test_signed_webhook_activates_without_browser(commerce):
    a=commerce;q=preview(a);pay(a,q);payment=captured(a,q);routes.gateway.get_payment_details.return_value=payment
    body=json.dumps({'event':'payment.captured','payload':{'payment':{'entity':payment}}}).encode()
    headers={'Content-Type':'application/json','X-Razorpay-Signature':hmac.new(a.config['SUBSCRIPTION_WEBHOOK_SECRET'].encode(),body,hashlib.sha256).hexdigest()}
    assert a.test_client().post('/api/subscription-payments/webhook',data=body).status_code==401
    for _ in range(2):assert a.test_client().post('/api/subscription-payments/webhook',data=body,headers=headers).status_code==200
    assert Subscription.query.count()==1 and SubscriptionCheckout.query.one().state=='paid'

@pytest.mark.parametrize('field,value',[('amount',1),('currency','USD'),('status','authorized'),('order_id','other')])
def test_rejects_invalid_provider_payment(commerce,field,value):
    a=commerce;q=preview(a);pay(a,q);payment=captured(a,q);payment[field]=value
    row=SubscriptionCheckout.query.one()
    with pytest.raises(ValueError):service.activate(row,payment)
    assert Subscription.query.count()==0


def test_tenant_auth_and_admin_catalog_validation(commerce,monkeypatch):
    a=commerce;c=a.test_client()
    assert c.post('/api/vendors/1/subscription/preview',json={}).status_code==401
    assert c.post('/api/vendors/1/subscription/preview',json={},headers=auth(a,2)).status_code==403
    monkeypatch.delenv('SUPER_ADMIN_API_KEY',raising=False)
    assert c.get('/api/packages/admin/catalog').status_code==401
    monkeypatch.setenv('SUPER_ADMIN_API_KEY','test-admin-key')
    data={'code':'base','name':'Base','pc_limit':5,'monthly':0,'quarterly':0,'yearly':0,'entitlements':['kiosk'],'features':[]}
    headers={'x-admin-key':'test-admin-key'}
    assert c.put('/api/packages/admin/catalog',json={'models':[dict(data,monthly='NaN')]},headers=headers).status_code==400
    assert c.put('/api/packages/admin/catalog',json={'models':[dict(data,pc_limit=2.5)]},headers=headers).status_code==400
    assert c.put('/api/packages/admin/catalog',json={'models':[data]},headers=headers).status_code==200
    assert Package.query.filter_by(code='base').one().features['price_inr']==0
    q=preview(a);assert pay(a,q).json['state']=='paid'
    routes.gateway.create_order.assert_not_called()


def test_expired_preview_and_changed_subscription_rejected(commerce):
    a=commerce;q=preview(a);row=db.session.get(SubscriptionCheckout,q['id']);row.expires_at=service.utcnow()-timedelta(seconds=1);db.session.commit()
    assert pay(a,q).status_code==400
    assert Subscription.query.count()==0


def test_renewal_preserves_remaining_days_and_each_invoice(commerce):
    a=commerce;q=preview(a);pay(a,q);finish(a,q)
    old_end=service._as_utc(Subscription.query.one().current_period_end)
    renewal=preview(a)
    assert renewal['action']=='renew' and datetime.fromisoformat(renewal['period_start'])==old_end
    routes.gateway.create_order.return_value={'id':'order_renew'};pay(a,renewal)
    payment=captured(a,renewal);payment['order_id']='order_renew';routes.gateway.get_order_payments.return_value=[payment]
    result=a.test_client().post(f'/api/vendors/1/subscription/purchases/{renewal["id"]}/reconcile',headers=auth(a))
    assert result.status_code==200,result.json
    assert Subscription.query.count()==1
    assert service._as_utc(Subscription.query.one().current_period_end)>old_end
    rows=a.test_client().get('/api/vendors/1/subscription/purchases',headers=auth(a)).json['purchases']
    assert len(rows)==2 and len({r['invoice_number'] for r in rows})==2


def test_feature_guard_and_expired_kiosk_capacity(commerce):
    from app.services.subscription_entitlements import enforce_entitlements
    a=commerce;q=preview(a);pay(a,q);finish(a,q)
    with a.test_request_context('/api/vendor/1/console-pricing'):
        assert enforce_entitlements() is None
    with a.test_request_context('/api/vendor/1/passes'):
        assert enforce_entitlements()[1]==403
    sub=Subscription.query.one();sub.current_period_end=service.utcnow()-timedelta(seconds=1);db.session.commit()
    assert get_vendor_pc_limit(1)==0


def test_second_pending_order_cannot_double_buy(commerce):
    a=commerce;first=preview(a);second=preview(a,'pro')
    assert pay(a,first).status_code==200
    assert pay(a,second).status_code==400
    routes.gateway.create_order.assert_called_once()


def test_invalid_cycle_quantity_and_cross_cafe_invoice(commerce):
    a=commerce;c=a.test_client()
    for data in [{'package_code':'base','extra_pcs':2.5},{'package_code':'base','billing_cycle':'invalid'}]:
        assert c.post('/api/vendors/1/subscription/preview',json=data,headers=auth(a)).status_code==400
    q=preview(a)
    assert c.get(f'/api/vendors/1/subscription/purchases/{q["id"]}/invoice',headers=auth(a,2)).status_code==403


def test_captured_payment_after_subscription_change_is_recorded_without_wrong_entitlement(commerce):
    a=commerce;q=preview(a);pay(a,q)
    # A separate admin grant changes the subscription while checkout is open.
    from app.services.subscription_service import create_subscription
    create_subscription(1,'pro',200,external_ref='admin-grant')
    result=finish(a,q)
    assert result['state']=='paid_unapplied' and result['invoice_number']
    assert service.get_active_subscription(1).package.code=='pro'
    assert finish(a,q)['state']=='paid_unapplied'
    assert Subscription.query.count()==1


def test_postgres_concurrent_webhooks_activate_once(commerce):
    if db.engine.dialect.name!='postgresql':pytest.skip('PostgreSQL row-lock regression')
    from concurrent.futures import ThreadPoolExecutor
    a=commerce;q=preview(a);pay(a,q);payment=captured(a,q);routes.gateway.get_payment_details.return_value=payment
    body=json.dumps({'event':'payment.captured','payload':{'payment':{'entity':payment}}}).encode()
    signature=hmac.new(a.config['SUBSCRIPTION_WEBHOOK_SECRET'].encode(),body,hashlib.sha256).hexdigest()
    db.session.remove()
    def deliver(_):
        with a.test_client() as client:
            response=client.post('/api/subscription-payments/webhook',data=body,headers={'Content-Type':'application/json','X-Razorpay-Signature':signature})
            return response.status_code
    with ThreadPoolExecutor(max_workers=4) as pool:assert list(pool.map(deliver,range(4)))==[200]*4
    assert Subscription.query.count()==1
    assert SubscriptionCheckout.query.one().state=='paid'


def test_postgres_concurrent_links_cannot_exceed_purchased_limit(commerce):
    if db.engine.dialect.name!='postgresql':pytest.skip('PostgreSQL capacity locking')
    from concurrent.futures import ThreadPoolExecutor
    from app.services.link_service import create_link
    a=commerce;base=Package.query.filter_by(code='base').one();base.pc_limit=2
    for n in range(1,5):db.session.add(Console(id=n,vendor_id=1,console_number=n,model_number='test',serial_number=str(n),brand='test',console_type='pc'))
    db.session.commit();q=preview(a);pay(a,q);finish(a,q);db.session.remove()
    def link(n):
        with a.app_context():
            row,error=create_link(1,n)
            return error is None
    with ThreadPoolExecutor(max_workers=4) as pool:assert sum(pool.map(link,range(1,5)))==2
    assert ConsoleLinkSession.query.filter_by(status='active').count()==2


def test_postgres_migration_rerun_preserves_purchased_terms(commerce):
    if db.engine.dialect.name!='postgresql':pytest.skip('PostgreSQL migration')
    from pathlib import Path
    a=commerce;q=preview(a);pay(a,q);finish(a,q)
    sub=Subscription.query.one();sub.commercial_terms=None;db.session.commit()
    script=(Path(__file__).resolve().parents[1]/'sql/20261001_subscription_commerce.sql').read_text()
    raw=db.engine.raw_connection()
    try:
        with raw.cursor() as cursor:cursor.execute(script)
        raw.commit();db.session.expire_all()
        assert Subscription.query.one().commercial_terms['pc_limit']==5
        p=Package.query.filter_by(code='base').one();p.pc_limit=99;db.session.commit()
        with raw.cursor() as cursor:cursor.execute(script)
        raw.commit();db.session.expire_all()
        assert Subscription.query.one().commercial_terms['pc_limit']==5
    finally:raw.close()
