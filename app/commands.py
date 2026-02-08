import click
from flask.cli import with_appcontext
from flask import current_app
from app.services.rawg_sync_service import RAWGSyncService


@click.command('sync-rawg-games')
@click.option('--pages', default=10, help='Number of pages (40 games per page)')
@click.option('--update/--no-update', default=True, help='Update existing games')
@with_appcontext
def sync_rawg_games_command(pages, update):
    """Sync games from RAWG API with images!"""
    click.echo(f"🚀 Syncing {pages} pages from RAWG ({pages * 40} games with images)...")
    
    result = RAWGSyncService.sync_games(max_pages=pages, update_existing=update)
    
    click.echo(f"""
    ✅ Complete!
    - Added: {result['added']} (with images!)
    - Updated: {result['updated']}
    - Errors: {result['errors']}
    """)


# 🆕 SUBSCRIPTION MANAGEMENT COMMANDS

@click.command('expire-subscriptions')
@with_appcontext
def expire_subscriptions_command():
    """
    Mark expired subscriptions as expired
    Run this command periodically (cron job or scheduler)
    
    Usage: flask expire-subscriptions
    """
    from app.services.subscription_service import expire_subscriptions
    
    click.echo("🔍 Checking for expired subscriptions...")
    count = expire_subscriptions()
    
    if count > 0:
        click.echo(f'✅ Expired {count} subscription(s)')
    else:
        click.echo("✓ No subscriptions to expire")


@click.command('list-subscriptions')
@click.option('--vendor-id', type=int, help='Filter by vendor ID')
@with_appcontext
def list_subscriptions_command(vendor_id):
    """
    List all subscriptions with status
    
    Usage: 
        flask list-subscriptions
        flask list-subscriptions --vendor-id=1
    """
    from app.models.subscription import Subscription
    from datetime import datetime, timezone
    
    query = Subscription.query
    
    if vendor_id:
        query = query.filter_by(vendor_id=vendor_id)
        click.echo(f"\n📋 Subscriptions for Vendor {vendor_id}:")
    else:
        click.echo("\n📋 All Subscriptions:")
    
    subs = query.order_by(Subscription.created_at.desc()).all()
    
    if not subs:
        click.echo("No subscriptions found.\n")
        return
    
    click.echo(f"\n{'ID':<5} {'Vendor':<8} {'Package':<15} {'Status':<10} {'Expires':<20} {'Paid':<10} {'Exp'}")
    click.echo("-" * 85)
    
    now = datetime.now(timezone.utc)
    
    for sub in subs:
        is_expired = sub.current_period_end <= now
        expired_marker = "✓" if is_expired else " "
        
        # Color coding for status
        status_display = sub.status.value
        if sub.status.value == 'active' and not is_expired:
            status_display = f"{sub.status.value} ✓"
        elif is_expired:
            status_display = f"{sub.status.value} ⚠"
        
        click.echo(
            f"{sub.id:<5} {sub.vendor_id:<8} {sub.package.code:<15} "
            f"{status_display:<10} {sub.current_period_end.strftime('%Y-%m-%d %H:%M'):<20} "
            f"₹{float(sub.unit_amount):<9.2f} {expired_marker}"
        )
    
    click.echo(f"\nTotal: {len(subs)} subscription(s)")
    
    # Summary
    active = sum(1 for s in subs if s.status.value == 'active' and s.current_period_end > now)
    expired = sum(1 for s in subs if s.current_period_end <= now)
    
    click.echo(f"Active: {active} | Expired: {expired}\n")


@click.command('test-subscription')
@click.argument('vendor_id', type=int)
@click.argument('package_code')
@with_appcontext
def test_subscription_command(vendor_id, package_code):
    """
    Create test subscription for development
    
    Usage: flask test-subscription 1 base
    """
    from app.services.subscription_service import create_subscription
    from app.models.vendor import Vendor
    from app.models.package import Package
    
    # Check if vendor exists
    vendor = Vendor.query.get(vendor_id)
    if not vendor:
        click.echo(f"❌ Error: Vendor {vendor_id} not found", err=True)
        return
    
    # Check if package exists
    package = Package.query.filter_by(code=package_code, active=True).first()
    if not package:
        click.echo(f"❌ Error: Package '{package_code}' not found or inactive", err=True)
        return
    
    try:
        sub = create_subscription(
            vendor_id=vendor_id,
            package_code=package_code,
            payment_amount=1.0,
            external_ref=f'test_{vendor_id}_{package_code}'
        )
        
        click.echo(f"✅ Created test subscription:")
        click.echo(f"   ID: {sub.id}")
        click.echo(f"   Vendor: {vendor.cafe_name} (ID: {vendor_id})")
        click.echo(f"   Package: {sub.package.name} ({package_code})")
        click.echo(f"   PC Limit: {sub.package.pc_limit}")
        click.echo(f"   Status: {sub.status.value}")
        click.echo(f"   Period: {sub.current_period_start.strftime('%Y-%m-%d')} to {sub.current_period_end.strftime('%Y-%m-%d')}")
        
        # Check dev mode
        if current_app.config.get('SUBSCRIPTION_DEV_MODE'):
            days = current_app.config.get('SUBSCRIPTION_TEST_DURATION_DAYS', 1)
            click.echo(f"   ⚠️  DEV MODE: Expires in {days} day(s)")
        
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)


@click.command('subscription-stats')
@with_appcontext
def subscription_stats_command():
    """
    Show subscription statistics
    
    Usage: flask subscription-stats
    """
    from app.models.subscription import Subscription, SubscriptionStatus
    from app.models.package import Package
    from datetime import datetime, timezone
    from sqlalchemy import func
    
    click.echo("\n📊 Subscription Statistics\n")
    
    now = datetime.now(timezone.utc)
    
    # Total subscriptions
    total = Subscription.query.count()
    click.echo(f"Total Subscriptions: {total}")
    
    # By status
    click.echo("\n📈 By Status:")
    status_counts = (
        Subscription.query
        .with_entities(Subscription.status, func.count(Subscription.id))
        .group_by(Subscription.status)
        .all()
    )
    for status, count in status_counts:
        click.echo(f"   {status.value}: {count}")
    
    # Active (not expired by time)
    active_count = (
        Subscription.query
        .filter(Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.trialing]))
        .filter(Subscription.current_period_end > now)
        .count()
    )
    click.echo(f"\n✅ Actually Active (not expired): {active_count}")
    
    # Needs expiry
    needs_expiry = (
        Subscription.query
        .filter(Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.trialing]))
        .filter(Subscription.current_period_end <= now)
        .count()
    )
    if needs_expiry > 0:
        click.echo(f"⚠️  Needs Expiry: {needs_expiry} (run: flask expire-subscriptions)")
    
    # By package
    click.echo("\n📦 By Package:")
    package_counts = (
        Subscription.query
        .join(Package)
        .with_entities(Package.code, Package.name, func.count(Subscription.id))
        .group_by(Package.code, Package.name)
        .all()
    )
    for code, name, count in package_counts:
        click.echo(f"   {name} ({code}): {count}")
    
    # Revenue
    total_revenue = (
        Subscription.query
        .with_entities(func.sum(Subscription.unit_amount))
        .scalar() or 0
    )
    click.echo(f"\n💰 Total Revenue: ₹{float(total_revenue):,.2f}")
    
    # Dev mode warning
    if current_app.config.get('SUBSCRIPTION_DEV_MODE'):
        click.echo(f"\n⚠️  DEV MODE ACTIVE:")
        click.echo(f"   - Test Price: ₹{current_app.config.get('SUBSCRIPTION_TEST_PRICE', 1)}")
        click.echo(f"   - Duration: {current_app.config.get('SUBSCRIPTION_TEST_DURATION_DAYS', 1)} day(s)")
    
    click.echo()


@click.command('fix-expired-subscriptions')
@with_appcontext
def fix_expired_subscriptions_command():
    """
    Fix all subscriptions that should be expired but aren't marked as such
    This is useful if cron job wasn't running
    
    Usage: flask fix-expired-subscriptions
    """
    from app.services.subscription_service import expire_subscriptions
    
    click.echo("🔧 Fixing expired subscriptions...")
    count = expire_subscriptions()
    
    if count > 0:
        click.echo(f"✅ Fixed {count} subscription(s)")
    else:
        click.echo("✓ All subscriptions are up to date")


# Register all commands
def register_commands(app):
    """Register all Flask CLI commands"""
    
    # RAWG sync command
    app.cli.add_command(sync_rawg_games_command)
    
    # Subscription management commands
    app.cli.add_command(expire_subscriptions_command)
    app.cli.add_command(list_subscriptions_command)
    app.cli.add_command(test_subscription_command)
    app.cli.add_command(subscription_stats_command)
    app.cli.add_command(fix_expired_subscriptions_command)
