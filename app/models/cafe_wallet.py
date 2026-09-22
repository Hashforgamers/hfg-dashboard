"""Cafe money is stored in integer paise; ledger and audit records are immutable."""
from datetime import datetime
from sqlalchemy import event
from app.extension.extensions import db


class CafePaymentPolicy(db.Model):
    __tablename__ = 'cafe_payment_policies'
    vendor_id = db.Column(db.Integer, primary_key=True)
    settings = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class CafeWallet(db.Model):
    __tablename__ = 'cafe_wallets'
    vendor_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, primary_key=True)
    balance = db.Column(db.BigInteger, nullable=False, default=0)
    reserved = db.Column(db.BigInteger, nullable=False, default=0)
    __table_args__ = (db.CheckConstraint('balance >= 0 AND reserved >= 0 AND balance >= reserved'),)


class CafeLedger(db.Model):
    __tablename__ = 'cafe_wallet_ledger'
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    kind = db.Column(db.String(32), nullable=False)
    amount = db.Column(db.BigInteger, nullable=False)
    balance_after = db.Column(db.BigInteger, nullable=False)
    reserved_after = db.Column(db.BigInteger, nullable=False)
    actor_id = db.Column(db.String(80), nullable=False)
    actor_name = db.Column(db.String(120), nullable=False)
    method = db.Column(db.String(32))
    shift_id = db.Column(db.String(36))
    session_id = db.Column(db.String(36))
    reversal_of = db.Column(db.Integer, unique=True)
    reason = db.Column(db.String(500), nullable=False)
    idempotency_key = db.Column(db.String(128), nullable=False)
    fingerprint = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint('vendor_id', 'idempotency_key'),)


class CafeAudit(db.Model):
    __tablename__ = 'cafe_activity_audit'
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, nullable=False, index=True)
    actor_id = db.Column(db.String(80), nullable=False)
    actor_name = db.Column(db.String(120), nullable=False)
    action = db.Column(db.String(64), nullable=False)
    details = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class CafeShift(db.Model):
    __tablename__ = 'cafe_staff_shifts'
    id = db.Column(db.String(36), primary_key=True)
    vendor_id = db.Column(db.Integer, nullable=False, index=True)
    actor_id = db.Column(db.String(80), nullable=False)
    actor_name = db.Column(db.String(120), nullable=False)
    open_key = db.Column(db.String(120), unique=True)
    opening_cash = db.Column(db.BigInteger, nullable=False)
    counted_cash = db.Column(db.BigInteger)
    expected_cash = db.Column(db.BigInteger)
    upi_receipts = db.Column(db.BigInteger)
    opened_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    closed_at = db.Column(db.DateTime)


class CafeStaffSession(db.Model):
    __tablename__ = 'cafe_staff_sessions'
    jti = db.Column(db.String(64), primary_key=True)
    vendor_id = db.Column(db.Integer, nullable=False, index=True)
    actor_id = db.Column(db.String(80), nullable=False)
    actor_name = db.Column(db.String(120), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    closed_at = db.Column(db.DateTime)


class CafePlaySession(db.Model):
    __tablename__ = 'cafe_play_sessions'
    id = db.Column(db.String(36), primary_key=True)
    vendor_id = db.Column(db.Integer, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=False)
    console_id = db.Column(db.Integer, nullable=False)
    link_id = db.Column(db.Integer, nullable=False)
    # Portable unique constraint: terminal sessions release their key to NULL.
    console_claim = db.Column(db.Integer, unique=True)
    idempotency_key = db.Column(db.String(128), nullable=False)
    fingerprint = db.Column(db.String(64), nullable=False)
    state = db.Column(db.String(24), nullable=False, default='reserved')
    kind = db.Column(db.String(24), nullable=False, default='wallet', server_default='wallet')
    booking_ids = db.Column(db.JSON, nullable=False, default=list, server_default='[]')
    booking_end = db.Column(db.DateTime)
    amount = db.Column(db.BigInteger, nullable=False)
    minutes = db.Column(db.Integer, nullable=False)
    command_token = db.Column(db.String(128), nullable=False)
    deadline = db.Column(db.DateTime, nullable=False)
    started_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint('vendor_id', 'user_id', 'idempotency_key'),
        db.Index('ix_cafe_play_deadline', 'state', 'deadline'),
        db.Index('ix_cafe_play_ends', 'state', 'ends_at'))


def immutable(mapper, connection, target):
    raise ValueError('Append-only record: create a reversal instead')


for model in (CafeLedger, CafeAudit):
    event.listen(model, 'before_update', immutable)
    event.listen(model, 'before_delete', immutable)


class CafeFoodOrder(db.Model):
    __tablename__ = 'cafe_food_orders'
    id = db.Column(db.String(36), primary_key=True)
    vendor_id = db.Column(db.Integer, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=False)
    items = db.Column(db.JSON, nullable=False)
    amount = db.Column(db.BigInteger, nullable=False)
    collector = db.Column(db.String(16), nullable=False)
    state = db.Column(db.String(24), nullable=False, default='pay_at_store')
    idempotency_key = db.Column(db.String(100), nullable=False)
    fingerprint = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint('vendor_id', 'user_id', 'idempotency_key'),)


class CafeBookingClaim(db.Model):
    __tablename__ = 'cafe_booking_claims'
    booking_id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
