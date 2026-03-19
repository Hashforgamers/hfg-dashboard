from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from sqlalchemy import and_
from flask import current_app
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.package import Package
from app.models.vendor import Vendor
from app.extension.extensions import db


BILLING_CYCLE_MONTHS = {
    "monthly": 1,
    "quarterly": 3,
    "yearly": 12,
}


def normalize_billing_cycle(value):
    cycle = str(value or "monthly").strip().lower()
    if cycle not in BILLING_CYCLE_MONTHS:
        return "monthly"
    return cycle


def get_subscription_duration(billing_cycle="monthly"):
    """
    Get subscription duration based on environment
    Returns: timedelta object
    """
    cycle = normalize_billing_cycle(billing_cycle)
    if current_app.config.get('SUBSCRIPTION_DEV_MODE', False):
        days = current_app.config.get('SUBSCRIPTION_TEST_DURATION_DAYS', 1)
        return timedelta(days=days)
    return relativedelta(months=BILLING_CYCLE_MONTHS[cycle])


def get_package_price_for_cycle(package, billing_cycle="monthly"):
    cycle = normalize_billing_cycle(billing_cycle)
    features = package.features or {}
    monthly_price = float(features.get('price_inr', 0) or 0)

    # Free packages stay free for any cycle.
    if monthly_price == 0:
        return 0.0

    if current_app.config.get('SUBSCRIPTION_DEV_MODE', False):
        return float(current_app.config.get('SUBSCRIPTION_TEST_PRICE', 1))

    if cycle == "quarterly":
        return float(features.get('quarterly_price_inr', monthly_price * 3) or 0)
    if cycle == "yearly":
        return float(features.get('yearly_price_inr', monthly_price * 12) or 0)
    return monthly_price


def get_active_subscription(vendor_id, ts=None):
    """
    Get currently active subscription for a vendor
    Checks status AND period validity
    """
    ts = ts or datetime.now(timezone.utc)
    return (Subscription.query
        .filter(Subscription.vendor_id == vendor_id)
        .filter(Subscription.status.in_([
            SubscriptionStatus.active, 
            SubscriptionStatus.trialing, 
            SubscriptionStatus.past_due
        ]))
        .filter(Subscription.current_period_start <= ts, Subscription.current_period_end > ts)
        .order_by(Subscription.current_period_end.desc())
        .first())


def is_subscription_active(vendor_id):
    """
    Check if vendor has an active, non-expired subscription
    
    Returns: 
        tuple: (bool: is_active, Subscription|None: subscription object)
    """
    now = datetime.now(timezone.utc)
    sub = get_active_subscription(vendor_id, now)
    
    if not sub:
        current_app.logger.info(f"Vendor {vendor_id}: No active subscription found")
        return False, None
    
    # Double-check period hasn't ended
    if sub.current_period_end <= now:
        current_app.logger.info(f"Vendor {vendor_id}: Subscription expired at {sub.current_period_end}")
        return False, sub
    
    current_app.logger.info(f"Vendor {vendor_id}: Active subscription until {sub.current_period_end}")
    return True, sub


def provision_default_subscription(vendor_id):
    """
    Create default subscription for new vendor
    Used during vendor onboarding
    """
    if get_active_subscription(vendor_id):
        current_app.logger.info(f"Vendor {vendor_id} already has active subscription")
        return
    
    # Get early_onboard free package (id=2 from your data)
    base_pkg = Package.query.filter_by(code='early_onboard', active=True).first()
    if not base_pkg:
        base_pkg = Package.query.filter_by(code='base', active=True).first_or_404()
    
    now = datetime.now(timezone.utc)
    duration = get_subscription_duration()
    
    sub = Subscription(
        vendor_id=vendor_id, 
        package_id=base_pkg.id,
        status=SubscriptionStatus.active,
        current_period_start=now,
        current_period_end=now + duration,
        unit_amount=0,
        currency='INR'
    )
    db.session.add(sub)
    db.session.commit()
    
    current_app.logger.info(f"Vendor {vendor_id}: Default subscription created (package: {base_pkg.code})")
    return sub


def create_subscription(vendor_id, package_code, payment_amount, external_ref=None, billing_cycle="monthly"):
    """
    Create a new subscription after successful payment
    
    Args:
        vendor_id: Vendor ID
        package_code: Package code (base, grow, elite)
        payment_amount: Amount paid in INR
        external_ref: Razorpay payment ID
    
    Returns:
        Subscription: New subscription object
    """
    now = datetime.now(timezone.utc)
    cycle = normalize_billing_cycle(billing_cycle)
    duration = get_subscription_duration(cycle)
    
    package = Package.query.filter_by(code=package_code, active=True).first()
    if not package:
        raise ValueError(f"Package {package_code} not found or inactive")
    
    # Idempotency: if this payment was already applied for this vendor, return existing row.
    if external_ref:
        existing_by_ref = (Subscription.query
            .filter(Subscription.vendor_id == vendor_id, Subscription.external_ref == external_ref)
            .order_by(Subscription.created_at.desc())
            .first())
        if existing_by_ref:
            current_app.logger.info(
                "Vendor %s: Reusing existing subscription %s for payment ref %s",
                vendor_id, existing_by_ref.id, external_ref
            )
            return existing_by_ref

    # Expire any "open" subscription statuses for this vendor regardless of period.
    # This keeps DB constraint uq_vendor_status(vendor_id, status) satisfied.
    open_statuses = [SubscriptionStatus.active, SubscriptionStatus.trialing, SubscriptionStatus.past_due]
    existing_open = (Subscription.query
        .filter(Subscription.vendor_id == vendor_id)
        .filter(Subscription.status.in_(open_statuses))
        .all())
    for sub in existing_open:
        sub.status = SubscriptionStatus.expired
        if sub.current_period_end is None or sub.current_period_end > now:
            sub.current_period_end = now
        sub.canceled_at = now
        current_app.logger.info(f"Vendor {vendor_id}: Expired old subscription {sub.id}")
    
    # Create new subscription
    new_sub = Subscription(
        vendor_id=vendor_id,
        package_id=package.id,
        status=SubscriptionStatus.active,
        current_period_start=now,
        current_period_end=now + duration,
        unit_amount=payment_amount,
        external_ref=external_ref,
        currency='INR'
    )
    
    db.session.add(new_sub)
    db.session.commit()
    
    current_app.logger.info(
        f"Vendor {vendor_id}: New subscription created "
        f"(package: {package.code}, amount: ₹{payment_amount}, "
        f"cycle: {cycle}, period: {now} to {now + duration})"
    )
    
    return new_sub


def renew_subscription(vendor_id, payment_amount, external_ref=None, billing_cycle="monthly"):
    """
    Renew existing subscription (keeps same package)
    
    Args:
        vendor_id: Vendor ID
        payment_amount: Amount paid in INR
        external_ref: Razorpay payment ID
    
    Returns:
        Subscription: Renewed subscription object
    """
    now = datetime.now(timezone.utc)
    cycle = normalize_billing_cycle(billing_cycle)
    duration = get_subscription_duration(cycle)
    
    # Idempotency: if this payment was already applied for this vendor, return existing row.
    if external_ref:
        existing_by_ref = (Subscription.query
            .filter(Subscription.vendor_id == vendor_id, Subscription.external_ref == external_ref)
            .order_by(Subscription.created_at.desc())
            .first())
        if existing_by_ref:
            current_app.logger.info(
                "Vendor %s: Reusing existing renewed subscription %s for payment ref %s",
                vendor_id, existing_by_ref.id, external_ref
            )
            return existing_by_ref

    # Get most recent subscription to determine package
    current = (Subscription.query
               .filter_by(vendor_id=vendor_id)
               .order_by(Subscription.created_at.desc())
               .first())
    
    if not current:
        raise ValueError(f"No existing subscription found for vendor {vendor_id}")
    
    package = current.package
    
    # Expire any "open" statuses before creating renewed record.
    open_statuses = [SubscriptionStatus.active, SubscriptionStatus.trialing, SubscriptionStatus.past_due]
    existing_open = (Subscription.query
        .filter(Subscription.vendor_id == vendor_id)
        .filter(Subscription.status.in_(open_statuses))
        .all())
    for sub in existing_open:
        sub.status = SubscriptionStatus.expired
        if sub.current_period_end is None or sub.current_period_end > now:
            sub.current_period_end = now
        sub.canceled_at = now
    
    # Create renewed subscription
    renewed = Subscription(
        vendor_id=vendor_id,
        package_id=package.id,
        status=SubscriptionStatus.active,
        current_period_start=now,
        current_period_end=now + duration,
        unit_amount=payment_amount,
        external_ref=external_ref,
        currency='INR'
    )
    
    db.session.add(renewed)
    db.session.commit()
    
    current_app.logger.info(
        f"Vendor {vendor_id}: Subscription renewed "
        f"(package: {package.code}, amount: ₹{payment_amount}, cycle: {cycle})"
    )
    
    return renewed


def change_subscription(vendor_id, package_code, immediate=True, unit_amount=0, cancel_current=False):
    """
    Change vendor's subscription package (Admin function)
    """
    now = datetime.now(timezone.utc)
    duration = get_subscription_duration()
    
    new_pkg = Package.query.filter_by(code=package_code, active=True).first_or_404()
    current = get_active_subscription(vendor_id, now)
    
    if immediate:
        if current:
            current.status = SubscriptionStatus.canceled if cancel_current else SubscriptionStatus.expired
            current.canceled_at = now
            current.current_period_end = now
        
        new = Subscription(
            vendor_id=vendor_id, 
            package_id=new_pkg.id,
            status=SubscriptionStatus.active,
            current_period_start=now,
            current_period_end=now + duration,
            unit_amount=unit_amount
        )
        db.session.add(new)
        db.session.commit()
        return new
    else:
        # Schedule at period end
        start_at = current.current_period_end if current else now
        new = Subscription(
            vendor_id=vendor_id, 
            package_id=new_pkg.id,
            status=SubscriptionStatus.active,
            current_period_start=start_at,
            current_period_end=start_at + duration,
            unit_amount=unit_amount
        )
        db.session.add(new)
        db.session.commit()
        return new


def get_vendor_pc_limit(vendor_id):
    """
    Get PC limit for vendor based on their subscription
    Returns default of 3 if no subscription found
    """
    sub = get_active_subscription(vendor_id)
    
    if sub and sub.package:
        return sub.package.pc_limit
    
    # Fallback to base package
    pkg = Package.query.filter_by(code='early_onboard', active=True).first()
    if not pkg:
        pkg = Package.query.filter_by(code='base', active=True).first()
    
    return pkg.pc_limit if pkg else 3


def expire_subscriptions():
    """
    Background job: Mark subscriptions as expired if period has ended
    
    Returns:
        int: Number of subscriptions expired
    """
    now = datetime.now(timezone.utc)
    
    # Find all subscriptions that should be expired
    expired_subs = (Subscription.query
                    .filter(Subscription.status.in_([
                        SubscriptionStatus.active,
                        SubscriptionStatus.trialing,
                        SubscriptionStatus.past_due
                    ]))
                    .filter(Subscription.current_period_end <= now)
                    .all())
    
    count = 0
    for sub in expired_subs:
        old_status = sub.status
        sub.status = SubscriptionStatus.expired
        count += 1
        current_app.logger.info(
            f"Expired subscription {sub.id} for vendor {sub.vendor_id} "
            f"(was: {old_status}, ended: {sub.current_period_end})"
        )
    
    if count > 0:
        db.session.commit()
        current_app.logger.info(f"Total subscriptions expired: {count}")
    
    return count


def get_package_price(package_code):
    """
    Get price for a package, respecting dev mode
    
    Args:
        package_code: Package code string
        
    Returns:
        float: Price in INR
    """
    # Get package first to check original price
    package = Package.query.filter_by(code=package_code, active=True).first()
    if not package:
        raise ValueError(f"Package {package_code} not found")
    
    return get_package_price_for_cycle(package, "monthly")
