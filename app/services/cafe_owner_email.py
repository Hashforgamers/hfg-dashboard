"""Transactional outbox: SMTP retries never undo an owner-approval request."""
from datetime import datetime, timedelta
from email.message import EmailMessage
import smtplib
import ssl
from flask import current_app
from app.extension.extensions import db
from app.models.cafe_wallet import CafeOwnerEmail, CafeContinuation, CafePlaySession


def send_owner_email(recipient, request, session):
    cfg=current_app.config
    if not cfg.get('MAIL_SERVER') or not cfg.get('MAIL_DEFAULT_SENDER'):
        raise RuntimeError('Owner email transport is not configured')
    if not recipient or '\n' in recipient or '\r' in recipient:
        raise RuntimeError('Owner email is missing or invalid')
    message=EmailMessage()
    message['From']=cfg['MAIL_DEFAULT_SENDER'];message['To']=recipient
    message['Subject']=f'Cafe continuation approval needed: PC {session.console_id}'
    message['Message-ID']=f'<cafe-continuation-{request.id}@hashforgamers.co.in>'
    message.set_content(f'Gamer {request.user_id} requests {request.minutes} more minutes on PC {session.console_id}.\n'
        f'Amount payable after play: INR {request.amount/100:.2f}.\n'
        'Open Live Sessions in your dashboard to accept or reject. Play stays stopped until approval.\n'
        f'Request expires at {request.expires_at.isoformat()} UTC.\n')
    klass=smtplib.SMTP_SSL if cfg.get('MAIL_USE_SSL') else smtplib.SMTP
    with klass(cfg['MAIL_SERVER'],int(cfg.get('MAIL_PORT',587)),timeout=10) as smtp:
        if cfg.get('MAIL_USE_TLS') and not cfg.get('MAIL_USE_SSL'): smtp.starttls(context=ssl.create_default_context())
        if cfg.get('MAIL_USERNAME'): smtp.login(cfg['MAIL_USERNAME'],cfg.get('MAIL_PASSWORD',''))
        smtp.send_message(message)


def dispatch_owner_emails():
    # SKIP LOCKED permits multiple reconcilers. A bounded SMTP timeout prevents
    # a broken provider holding financial/session locks (this transaction owns none).
    now=datetime.utcnow()
    rows=CafeOwnerEmail.query.filter(CafeOwnerEmail.sent_at.is_(None),
        CafeOwnerEmail.next_attempt_at<=now,CafeOwnerEmail.attempts<8).order_by(
        CafeOwnerEmail.next_attempt_at).limit(5).with_for_update(skip_locked=True).all()
    for row in rows:
        request=db.session.get(CafeContinuation,row.request_id)
        if not request or request.state!='pending' or request.expires_at<=now:
            row.last_error='Request no longer pending';row.attempts=8
            continue
        try:
            send_owner_email(row.recipient,request,db.session.get(CafePlaySession,request.parent_id))
            row.sent_at=datetime.utcnow();row.last_error=None
        except Exception:
            row.last_error='Email delivery failed; verify owner email and SMTP configuration'
            current_app.logger.warning('Owner email failed request=%s',row.request_id)
        row.attempts+=1;row.next_attempt_at=datetime.utcnow()+timedelta(seconds=min(300,15*2**row.attempts))
    db.session.commit()
