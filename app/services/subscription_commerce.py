"""Server-priced subscription quotes, prorated upgrades and immutable invoices."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from dateutil.relativedelta import relativedelta
from app.extension.extensions import db
from app.models.package import Package
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_checkout import SubscriptionCheckout
from app.models.vendor import Vendor
from app.models.console_link_session import ConsoleLinkSession
from app.services.subscription_service import get_active_subscription, _as_utc, get_package_price_for_cycle
from app.services.pricing_math import money

FEATURES = {'kiosk':'PC kiosk', 'pricing':'Console pricing', 'cafe_wallet':'Cafe wallet',
            'passes':'Passes', 'food':'Food and extras', 'analytics':'Analytics',
            'tournaments':'Tournaments', 'staff':'Staff management'}
CYCLES = {'monthly':1, 'quarterly':3, 'yearly':12}


def utcnow():
    return datetime.now(timezone.utc)


def paise(value):
    return int((money(value)*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def terms(sub):
    if sub.commercial_terms:
        return dict(sub.commercial_terms)
    features = sub.package.features or {}
    return dict(package_code=sub.package.code, package_name=sub.package.name,
                pc_limit=sub.package.pc_limit, extra_pcs=0, billing_cycle='monthly',
                recurring_paise=paise(sub.unit_amount or 0), entitlements=features.get('entitlements', list(FEATURES)),
                extra_pc_monthly=features.get('extra_pc_monthly',0))


def preview(vendor_id, data):
    if not isinstance(data,dict): raise ValueError('Supply a JSON object')
    cycle = data.get('billing_cycle','monthly')
    if cycle not in CYCLES: raise ValueError('Choose monthly, quarterly or yearly')
    extra = data.get('extra_pcs',0)
    if type(extra) is not int or not 0 <= extra <= 10000: raise ValueError('Extra PCs must be a whole number from 0 to 10000')
    vendor = db.session.get(Vendor,vendor_id)
    if not vendor: raise ValueError('Cafe not found')
    package = Package.query.filter_by(code=data.get('package_code'),active=True).first()
    if not package: raise ValueError('Plan is unavailable')
    now = utcnow(); current = get_active_subscription(vendor_id)
    f=package.features or {}; extra_price=money(f.get('extra_pc_monthly',0))
    if extra and extra_price <= 0: raise ValueError('This plan does not offer additional PCs; choose a larger plan')
    recurring = paise(get_package_price_for_cycle(package,cycle)) + paise(extra_price)*extra*CYCLES[cycle]
    target = dict(package_code=package.code,package_name=package.name,pc_limit=package.pc_limit+extra,
                  extra_pcs=extra,billing_cycle=cycle,recurring_paise=recurring,
                  extra_pc_monthly=float(extra_price),entitlements=f.get('entitlements',list(FEATURES)))
    if target['pc_limit']>10000: raise ValueError('Total PC capacity cannot exceed 10000')
    if extra and 'kiosk' not in target['entitlements']: raise ValueError('Additional PCs require the kiosk feature')
    active_links=ConsoleLinkSession.query.filter_by(vendor_id=vendor_id,status='active').count()
    if target['pc_limit'] < active_links: raise ValueError('Unlink PCs above the new plan limit before changing plans')
    if active_links and 'kiosk' not in target['entitlements']: raise ValueError('Unlink kiosks before selecting a plan without kiosk access')
    action='new'; charge=recurring; start=now; end=now+relativedelta(months=CYCLES[cycle])
    if current:
        old=terms(current)
        same = (old['package_code']==package.code and old.get('extra_pcs',0)==extra
                and old['pc_limit']==target['pc_limit'] and set(old['entitlements'])==set(target['entitlements'])
                and old['recurring_paise']==recurring)
        if same:
            if cycle != old['billing_cycle']: raise ValueError('Keep the current billing cycle until this subscription expires')
            action='renew'; start=_as_utc(current.current_period_end); end=start+relativedelta(months=CYCLES[cycle])
        else:
            action='upgrade'
            if cycle != old['billing_cycle']: raise ValueError('Keep the current billing cycle for a prorated upgrade')
            if target['pc_limit'] < old['pc_limit'] or not set(old['entitlements']).issubset(target['entitlements']):
                raise ValueError('Mid-period changes must retain existing PCs and features; contact Hash for a downgrade')
            difference=recurring-old['recurring_paise']
            if difference <= 0: raise ValueError('Select a higher-priced plan or add PCs for an upgrade')
            end=_as_utc(current.current_period_end)
            period_start=datetime.fromisoformat(old['cycle_start']) if old.get('cycle_start') else _as_utc(current.current_period_start)
            cycle_end=datetime.fromisoformat(old['cycle_end']) if old.get('cycle_end') else end
            duration=Decimal(str((cycle_end-period_start).total_seconds()))
            if duration <= 0: raise ValueError('Invalid existing billing period; contact Hash support')
            remaining=Decimal(str((end-now).total_seconds()))
            charge=int((Decimal(difference)*remaining/duration).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            target['cycle_start']=period_start.isoformat()
            target['cycle_end']=cycle_end.isoformat()
    target.setdefault('cycle_start',start.isoformat())
    target.setdefault('cycle_end',end.isoformat())
    snapshot=dict(terms=target,action=action,amount_paise=charge,currency='INR',
                  period_start=start.isoformat(),period_end=end.isoformat(),base_subscription_id=current.id if current else None,
                  base_period_end=current.current_period_end.isoformat() if current else None,
                  customer=dict(vendor_id=vendor_id,cafe_name=vendor.cafe_name),
                  description='Prorated difference; existing renewal date retained' if action=='upgrade' else 'Full billing period',
                  tax_note='Total payable as configured by Hash. No separate tax breakdown is applied.')
    checkout=SubscriptionCheckout(id=str(uuid4()),vendor_id=vendor_id,package_id=package.id,snapshot=snapshot,
        state='preview',created_at=now,expires_at=now+timedelta(minutes=15))
    db.session.add(checkout);db.session.commit()
    return checkout


def public_quote(row):
    return dict(id=row.id,state=row.state,expires_at=_as_utc(row.expires_at).isoformat(),
                order_id=row.order_id,payment_id=row.payment_id,subscription_id=row.subscription_id,
                invoice_number=('HFG-SUB-'+row.id.upper()) if row.paid_at else None,
                paid_at=_as_utc(row.paid_at).isoformat() if row.paid_at else None,**row.snapshot)


def lock_vendor(vendor_id):
    return Vendor.query.filter_by(id=vendor_id).with_for_update().one()


def check_base(row):
    current=get_active_subscription(row.vendor_id)
    expected=row.snapshot['base_subscription_id']
    if (current.id if current else None) != expected:
        raise ValueError('Subscription changed since this preview. Generate a new preview.')
    if current and current.current_period_end.isoformat()!=row.snapshot['base_period_end']:
        raise ValueError('Subscription period changed. Generate a new preview.')
    return current


def activate(row, payment=None):
    """Caller holds vendor lock; activation, receipt and invoice commit together."""
    if row.state in {'paid','paid_unapplied'}: return row
    if payment:
        if payment.get('order_id')!=row.order_id or payment.get('status')!='captured' or payment.get('currency')!='INR' or payment.get('amount')!=row.snapshot['amount_paise']:
            raise ValueError('Payment is not a captured payment for this order and amount')
        if SubscriptionCheckout.query.filter_by(payment_id=payment['id']).filter(SubscriptionCheckout.id!=row.id).first():
            raise ValueError('Payment already used')
    elif row.snapshot['amount_paise'] != 0: raise ValueError('Payment required')
    now=utcnow()
    try:
        current=check_base(row)
        if datetime.fromisoformat(row.snapshot['period_end'])<=now:
            raise ValueError('The purchased period has ended before activation')
    except ValueError as error:
        if not payment: raise
        row.payment_id=payment['id'];row.paid_at=now;row.state='paid_unapplied'
        row.snapshot=dict(row.snapshot,activation_error=str(error))
        db.session.commit()
        return row
    target=row.snapshot['terms']; action=row.snapshot['action']
    if action=='renew' and current:
        # Extend the current entitlement; the invoice separately records the purchased future period.
        sub=current;sub.current_period_end=datetime.fromisoformat(row.snapshot['period_end'])
        saved=terms(sub);saved.setdefault('cycle_start',_as_utc(sub.current_period_start).isoformat());saved.setdefault('cycle_end',row.snapshot['base_period_end']);saved['recurring_paise']=target['recurring_paise'];saved['billing_cycle']=target['billing_cycle']
        # Keep cycle_start for upgrades until the prepaid period begins.
        sub.commercial_terms=saved
    else:
        for old in Subscription.query.filter_by(vendor_id=row.vendor_id).filter(Subscription.status.in_([SubscriptionStatus.active,SubscriptionStatus.trialing,SubscriptionStatus.past_due])).all():
            old.status=SubscriptionStatus.expired;old.canceled_at=now
        db.session.flush()
        sub=Subscription(vendor_id=row.vendor_id,package_id=row.package_id,status=SubscriptionStatus.active,
            current_period_start=now,current_period_end=datetime.fromisoformat(row.snapshot['period_end']),
            unit_amount=Decimal(row.snapshot['amount_paise'])/100,currency='INR',
            external_ref=payment['id'] if payment else 'free:'+row.id,commercial_terms=target)
        db.session.add(sub);db.session.flush()
    row.subscription_id=sub.id;row.payment_id=payment['id'] if payment else None;row.paid_at=now;row.state='paid'
    db.session.commit()
    return row
