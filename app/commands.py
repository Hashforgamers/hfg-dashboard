import click
from flask.cli import with_appcontext
from flask import current_app
from sqlalchemy import text
from werkzeug.security import generate_password_hash
from app.extension.extensions import db
from app.services.rawg_sync_service import RAWGSyncService
from app.models.vendor import Vendor
from app.models.vendorStaff import VendorStaff
from app.models.vendorRolePermission import VendorRolePermission
from app.services.rbac_service import DEFAULT_ROLE_PERMISSIONS, generate_unique_pin


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


@click.command('init-pc-link-table')
@with_appcontext
def init_pc_link_table_command():
    """
    Create console_link_sessions table and indexes if they don't exist.

    Usage:
        flask init-pc-link-table
    """
    statements = [
        """
        CREATE TABLE IF NOT EXISTS console_link_sessions (
            id SERIAL PRIMARY KEY,
            vendor_id INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
            console_id INTEGER NOT NULL REFERENCES consoles(id) ON DELETE CASCADE,
            kiosk_id VARCHAR(64) NULL,
            session_token VARCHAR(128) NOT NULL UNIQUE,
            status VARCHAR(16) NOT NULL DEFAULT 'active',
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ended_at TIMESTAMPTZ NULL,
            close_reason VARCHAR(64) NULL
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_console_link_sessions_vendor_id ON console_link_sessions (vendor_id);",
        "CREATE INDEX IF NOT EXISTS ix_console_link_sessions_console_id ON console_link_sessions (console_id);",
        "CREATE INDEX IF NOT EXISTS ix_console_link_sessions_status ON console_link_sessions (status);",
        "CREATE INDEX IF NOT EXISTS ix_console_link_sessions_session_token ON console_link_sessions (session_token);",
        "CREATE INDEX IF NOT EXISTS ix_cls_vendor_active ON console_link_sessions (vendor_id, status);",
        "CREATE INDEX IF NOT EXISTS ix_cls_console_active ON console_link_sessions (console_id, status);",
    ]

    try:
        with db.engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
        click.echo("✓ console_link_sessions table is ready")
    except Exception as e:
        click.echo(f"❌ Failed to initialize console_link_sessions: {e}", err=True)


@click.command('init-review-table')
@with_appcontext
def init_review_table_command():
    """
    Create cafe_reviews table and indexes if they don't exist.

    Usage:
        flask init-review-table
    """
    statements = [
        """
        CREATE TABLE IF NOT EXISTS cafe_reviews (
            id UUID PRIMARY KEY,
            vendor_id INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            booking_id INTEGER NULL REFERENCES bookings(id) ON DELETE SET NULL,
            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
            title VARCHAR(120) NULL,
            comment TEXT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'published',
            is_anonymous BOOLEAN NOT NULL DEFAULT FALSE,
            user_name_snapshot VARCHAR(120) NULL,
            user_avatar_snapshot VARCHAR(255) NULL,
            response_text TEXT NULL,
            responded_at TIMESTAMPTZ NULL,
            responded_by VARCHAR(120) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_cafe_reviews_booking_id UNIQUE (booking_id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_cafe_reviews_vendor_id ON cafe_reviews (vendor_id);",
        "CREATE INDEX IF NOT EXISTS ix_cafe_reviews_vendor_status ON cafe_reviews (vendor_id, status);",
        "CREATE INDEX IF NOT EXISTS ix_cafe_reviews_user_id ON cafe_reviews (user_id);",
        "CREATE INDEX IF NOT EXISTS ix_cafe_reviews_created_at ON cafe_reviews (created_at);",
    ]

    try:
        with db.engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
        click.echo("✓ cafe_reviews table is ready")
    except Exception as e:
        click.echo(f"❌ Failed to initialize cafe_reviews: {e}", err=True)


@click.command('init-rbac-tables')
@with_appcontext
def init_rbac_tables_command():
    """
    Create RBAC tables if they do not exist.

    Usage:
        flask init-rbac-tables
    """
    statements = [
        """
        CREATE TABLE IF NOT EXISTS vendor_staff (
            id SERIAL PRIMARY KEY,
            vendor_id INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
            name VARCHAR(120) NOT NULL,
            role VARCHAR(32) NOT NULL DEFAULT 'staff',
            pin_code VARCHAR(6) NULL,
            pin_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_vendor_staff_name UNIQUE (vendor_id, name)
        );
        """,
        "ALTER TABLE vendor_staff ADD COLUMN IF NOT EXISTS pin_code VARCHAR(6);",
        "CREATE INDEX IF NOT EXISTS ix_vendor_staff_vendor_id ON vendor_staff (vendor_id);",
        "CREATE INDEX IF NOT EXISTS ix_vendor_staff_role ON vendor_staff (role);",
        """
        CREATE TABLE IF NOT EXISTS vendor_role_permissions (
            id SERIAL PRIMARY KEY,
            vendor_id INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
            role VARCHAR(32) NOT NULL,
            permission VARCHAR(64) NOT NULL,
            CONSTRAINT uq_vendor_role_permission UNIQUE (vendor_id, role, permission)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_vendor_role_permissions_vendor_id ON vendor_role_permissions (vendor_id);",
        "CREATE INDEX IF NOT EXISTS ix_vendor_role_permissions_role ON vendor_role_permissions (role);",
    ]

    try:
        with db.engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
        click.echo("✓ RBAC tables are ready")
    except Exception as e:
        click.echo(f"❌ Failed to initialize RBAC tables: {e}", err=True)


@click.command('migrate-rbac-legacy')
@click.option('--vendor-id', type=int, default=None, help='Migrate only a specific vendor ID')
@click.option('--dry-run', is_flag=True, help='Preview migration without writing changes')
@with_appcontext
def migrate_rbac_legacy_command(vendor_id, dry_run):
    """
    Backfill RBAC for legacy vendors:
    1) Ensure one owner staff account exists per vendor
    2) Seed default role-permission rows if missing

    Usage:
        flask migrate-rbac-legacy
        flask migrate-rbac-legacy --vendor-id=14
        flask migrate-rbac-legacy --dry-run
    """
    query = Vendor.query
    if vendor_id is not None:
        query = query.filter(Vendor.id == vendor_id)

    vendors = query.order_by(Vendor.id.asc()).all()
    if not vendors:
        click.echo("No vendors found for migration.")
        return

    created_owner_count = 0
    seeded_perm_count = 0
    unchanged_count = 0
    owner_pin_rows = []

    for vendor in vendors:
        changed = False

        owner_staff = VendorStaff.query.filter_by(vendor_id=vendor.id, role='owner').first()
        if not owner_staff:
            generated_pin = generate_unique_pin(vendor.id)
            owner_name = (vendor.owner_name or "Owner").strip() or "Owner"

            if not dry_run:
                db.session.add(
                    VendorStaff(
                        vendor_id=vendor.id,
                        name=owner_name,
                        role='owner',
                        pin_hash=generate_password_hash(generated_pin),
                        is_active=True,
                    )
                )

            created_owner_count += 1
            changed = True
            owner_pin_rows.append((vendor.id, vendor.cafe_name, owner_name, generated_pin))

        existing_perm_count = VendorRolePermission.query.filter_by(vendor_id=vendor.id).count()
        if existing_perm_count == 0:
            if not dry_run:
                for role, permissions in DEFAULT_ROLE_PERMISSIONS.items():
                    for permission in permissions:
                        db.session.add(
                            VendorRolePermission(
                                vendor_id=vendor.id,
                                role=role,
                                permission=permission,
                            )
                        )
            seeded_perm_count += 1
            changed = True

        if not changed:
            unchanged_count += 1

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    click.echo("\nRBAC legacy migration summary")
    click.echo("--------------------------------")
    click.echo(f"Vendors scanned: {len(vendors)}")
    click.echo(f"Owner staff created: {created_owner_count}")
    click.echo(f"Role-permission sets seeded: {seeded_perm_count}")
    click.echo(f"Unchanged vendors: {unchanged_count}")
    click.echo(f"Mode: {'DRY RUN' if dry_run else 'APPLIED'}")

    if owner_pin_rows:
        click.echo("\nGenerated owner PINs (save securely):")
        click.echo("vendor_id | cafe_name | owner_name | pin")
        for row in owner_pin_rows:
            click.echo(f"{row[0]} | {row[1]} | {row[2]} | {row[3]}")
    else:
        click.echo("\nNo new owner PINs were generated.")


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
    app.cli.add_command(init_pc_link_table_command)
    app.cli.add_command(init_review_table_command)
    app.cli.add_command(init_rbac_tables_command)
    app.cli.add_command(migrate_rbac_legacy_command)
