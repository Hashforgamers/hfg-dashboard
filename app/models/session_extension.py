"""Shared kiosk continuation records. Money remains integer paise."""
from datetime import datetime
from app.extension.extensions import db

class SessionExtensionPolicy(db.Model):
    __tablename__ = 'session_extension_policies'
    vendor_id = db.Column(db.Integer, primary_key=True)
    credit_mode = db.Column(db.String(24), nullable=False, default='automatic')
    credit_limit = db.Column(db.BigInteger)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class RuntimeSession(db.Model):
    __tablename__ = 'kiosk_runtime_sessions'
    id = db.Column(db.String(36), primary_key=True)
    vendor_id = db.Column(db.Integer, nullable=False, index=True)
    console_id = db.Column(db.Integer, nullable=False)
    link_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    console_claim = db.Column(db.Integer, unique=True)
    source_kind = db.Column(db.String(16), nullable=False)
    source_id = db.Column(db.String(36), nullable=False)
    booking_ids = db.Column(db.JSON, nullable=False, default=list)
    started_at = db.Column(db.DateTime, nullable=False)
    paid_until = db.Column(db.DateTime, nullable=False)
    reserved_until = db.Column(db.DateTime, nullable=False)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    billed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)
    stop_at = db.Column(db.DateTime)
    rolling = db.Column(db.Boolean, nullable=False, default=False)
    credit_consent = db.Column(db.Boolean, nullable=False, default=False)
    credit_mode = db.Column(db.String(24), nullable=False)
    credit_limit = db.Column(db.BigInteger)
    revision = db.Column(db.Integer, nullable=False, default=1)
    event_sequence = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(32), nullable=False, default='active')
    reason = db.Column(db.String(80))
    notice_boundary = db.Column(db.DateTime)
    __table_args__ = (db.UniqueConstraint('source_kind','source_id','console_id'),)

class ExtensionSegment(db.Model):
    __tablename__ = 'kiosk_extension_segments'
    id = db.Column(db.String(36), primary_key=True)
    runtime_id = db.Column(db.String(36), db.ForeignKey('kiosk_runtime_sessions.id'), nullable=False, index=True)
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    amount = db.Column(db.BigInteger, nullable=False)
    funding = db.Column(db.BigInteger, nullable=False, default=0)
    captured = db.Column(db.BigInteger, nullable=False, default=0)
    charged = db.Column(db.BigInteger, nullable=False, default=0)
    credit_due = db.Column(db.BigInteger, nullable=False, default=0)
    credit_paid = db.Column(db.BigInteger, nullable=False, default=0)
    closed = db.Column(db.Boolean, nullable=False, default=False)
    __table_args__ = (db.UniqueConstraint('runtime_id','starts_at'),
        db.CheckConstraint('amount >= 0 AND funding >= 0 AND funding <= amount AND captured >= 0 AND captured <= funding AND charged >= 0 AND charged <= amount AND credit_due >= 0 AND credit_paid >= 0 AND credit_paid <= credit_due'),)

class ExtensionQuote(db.Model):
    __tablename__ = 'kiosk_extension_quotes'
    id = db.Column(db.String(36), primary_key=True)
    runtime_id = db.Column(db.String(36), db.ForeignKey('kiosk_runtime_sessions.id'), nullable=False, index=True)
    revision = db.Column(db.Integer, nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    amount = db.Column(db.BigInteger, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(24), nullable=False, default='quoted')
    pricing_basis = db.Column(db.JSON)
    idempotency_key = db.Column(db.String(100), unique=True)
    fingerprint = db.Column(db.String(64))

class SessionNotice(db.Model):
    __tablename__ = 'kiosk_session_notices'
    id = db.Column(db.String(36), primary_key=True)
    vendor_id = db.Column(db.Integer, nullable=False, index=True)
    runtime_id = db.Column(db.String(36), db.ForeignKey('kiosk_runtime_sessions.id'), nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    details = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)
    dedupe_key = db.Column(db.String(150), unique=True)

class SessionOutbox(db.Model):
    __tablename__ = 'kiosk_session_outbox'
    id = db.Column(db.String(36), primary_key=True)
    runtime_id = db.Column(db.String(36), db.ForeignKey('kiosk_runtime_sessions.id'), nullable=False)
    revision = db.Column(db.Integer, nullable=False)
    snapshot = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    published_at = db.Column(db.DateTime)
    __table_args__ = (db.Index('ix_kiosk_outbox_pending','published_at','created_at'),)

class SessionReceipt(db.Model):
    __tablename__ = 'kiosk_session_receipts'
    id = db.Column(db.String(36), primary_key=True)
    runtime_id = db.Column(db.String(36), db.ForeignKey('kiosk_runtime_sessions.id'), nullable=False, index=True)
    vendor_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.BigInteger, nullable=False)
    method = db.Column(db.String(24), nullable=False)
    actor_id = db.Column(db.String(80), nullable=False)
    idempotency_key = db.Column(db.String(100), nullable=False)
    fingerprint = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('vendor_id','idempotency_key'),)

class RuntimeMutation(db.Model):
    __tablename__ = 'kiosk_runtime_mutations'
    runtime_id = db.Column(db.String(36), primary_key=True)
    idempotency_key = db.Column(db.String(100), primary_key=True)
    fingerprint = db.Column(db.String(64), nullable=False)


class SessionCreditEntry(db.Model):
    __tablename__ = 'kiosk_session_credit_ledger'
    id = db.Column(db.String(36), primary_key=True)
    runtime_id = db.Column(db.String(36), db.ForeignKey('kiosk_runtime_sessions.id'), nullable=False, index=True)
    segment_id = db.Column(db.String(36), db.ForeignKey('kiosk_extension_segments.id'), nullable=False)
    amount = db.Column(db.BigInteger, nullable=False)
    kind = db.Column(db.String(24), nullable=False)
    idempotency_key = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

from sqlalchemy import event

def append_only(mapper,connection,target):
    raise ValueError('Append-only financial record; create a reversal instead')

for record in (SessionCreditEntry,SessionReceipt):
    event.listen(record,'before_update',append_only)
    event.listen(record,'before_delete',append_only)

class BaseSlotRelease(db.Model):
    __tablename__ = 'kiosk_base_slot_releases'
    booking_id = db.Column(db.Integer, primary_key=True)
    console_id = db.Column(db.Integer, primary_key=True)
    runtime_id = db.Column(db.String(36), db.ForeignKey('kiosk_runtime_sessions.id'), nullable=False)
    units = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
