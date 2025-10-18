from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import and_
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.package import Package
from app.models.vendor import Vendor
from app.extension.extensions import db

def get_active_subscription(vendor_id, ts=None):
    ts = ts or datetime.utcnow()
    return (Subscription.query
        .filter(Subscription.vendor_id == vendor_id)
        .filter(Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.trialing, SubscriptionStatus.past_due]))
        .filter(Subscription.current_period_start <= ts, Subscription.current_period_end > ts)
        .order_by(Subscription.current_period_end.desc())
        .first())

def provision_default_subscription(vendor_id):
    if get_active_subscription(vendor_id):
        return
    base_pkg = Package.query.filter_by(code='base', active=True).first_or_404()
    now = datetime.utcnow()
    sub = Subscription(
        vendor_id=vendor_id, package_id=base_pkg.id,
        status=SubscriptionStatus.active,
        current_period_start=now,
        current_period_end=now + relativedelta(months=1),
        unit_amount=0
    )
    db.session.add(sub)
    db.session.commit()

def change_subscription(vendor_id, package_code, immediate=True, unit_amount=0, cancel_current=False):
    now = datetime.utcnow()
    new_pkg = Package.query.filter_by(code=package_code, active=True).first_or_404()
    current = get_active_subscription(vendor_id, now)
    if immediate:
        if current:
            current.status = SubscriptionStatus.canceled if cancel_current else SubscriptionStatus.expired
            current.canceled_at = now
            current.current_period_end = now
        new = Subscription(
            vendor_id=vendor_id, package_id=new_pkg.id,
            status=SubscriptionStatus.active,
            current_period_start=now,
            current_period_end=now + relativedelta(months=1),
            unit_amount=unit_amount
        )
        db.session.add(new)
        db.session.commit()
        return new
    else:
        # schedule at period end
        start_at = current.current_period_end if current else now
        new = Subscription(
            vendor_id=vendor_id, package_id=new_pkg.id,
            status=SubscriptionStatus.active,
            current_period_start=start_at,
            current_period_end=start_at + relativedelta(months=1),
            unit_amount=unit_amount
        )
        db.session.add(new)
        db.session.commit()
        return new

def get_vendor_pc_limit(vendor_id):
    sub = get_active_subscription(vendor_id)
    pkg = sub.package if sub else Package.query.filter_by(code='base', active=True).first()
    if not pkg:
        return 3
    return pkg.pc_limit
