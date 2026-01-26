from datetime import datetime, timedelta
import secrets
from sqlalchemy import func
from app.extension.extensions import db
from app.models.console_link_session import ConsoleLinkSession
from app.models.console import Console
from .subscription_service import get_vendor_pc_limit

def count_active_links(vendor_id):
    return db.session.query(func.count(ConsoleLinkSession.id)).filter_by(
        vendor_id=vendor_id, status='active'
    ).scalar()

def pc_is_linked(console_id):
    return db.session.query(ConsoleLinkSession.id).filter_by(
        console_id=console_id, status='active'
    ).first() is not None

def list_vendor_pcs(vendor_id):
    return Console.query.filter_by(vendor_id=vendor_id, console_type='pc').order_by(Console.console_number.asc()).all()

def create_link(vendor_id, console_id, kiosk_id=None):
    with db.session.begin_nested():
        limit = get_vendor_pc_limit(vendor_id)
        active = count_active_links(vendor_id)
        if active >= limit:
            return None, "Plan limit reached"

        console = Console.query.filter_by(id=console_id, vendor_id=vendor_id, console_type='pc').with_for_update().first()
        if not console:
            return None, "Console not found"
        if pc_is_linked(console_id):
            return None, "Console already linked"

        token = secrets.token_urlsafe(24)
        sess = ConsoleLinkSession(
            vendor_id=vendor_id, console_id=console_id,
            started_at=datetime.utcnow(), status='active',
            session_token=token, kiosk_id=kiosk_id
        )
        db.session.add(sess)
    db.session.commit()
    return sess, None

def close_link(session_id=None, console_id=None, vendor_id=None, reason=None):
    q = ConsoleLinkSession.query.filter_by(status='active')
    if session_id:
        q = q.filter_by(id=session_id)
    if console_id:
        q = q.filter_by(console_id=console_id)
    if vendor_id:
        q = q.filter_by(vendor_id=vendor_id)
    sess = q.first()
    if not sess:
        return 0
    sess.status = 'closed'
    sess.ended_at = datetime.utcnow()
    sess.close_reason = reason
    db.session.commit()
    return 1
