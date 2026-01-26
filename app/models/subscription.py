# models/subscription.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, UniqueConstraint, Index, Numeric, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.extension.extensions import db
import enum

from app.models.package import Package

class SubscriptionStatus(str, enum.Enum):
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    expired = "expired"

class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False, index=True)
    package_id = Column(Integer, ForeignKey('packages.id', ondelete='RESTRICT'), nullable=False)
    status = Column(Enum(SubscriptionStatus), nullable=False, index=True, default=SubscriptionStatus.active)
    current_period_start = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    current_period_end = Column(DateTime(timezone=True), nullable=False)   # next renewal/end
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    trial_end = Column(DateTime(timezone=True), nullable=True)

    # billing metadata (optional, for proration/invoicing)
    currency = Column(String(8), nullable=False, default='INR')
    unit_amount = Column(Numeric(12,2), nullable=False, default=0)   # monthly price incl. tax if needed
    external_ref = Column(String(64), nullable=True)                 # gateway sub id

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    vendor = relationship('Vendor', back_populates='subscriptions')
    package = relationship('Package')

    __table_args__ = (
        # At most one non-expired active/trialing/past_due subscription per vendor
        UniqueConstraint('vendor_id', 'status', name='uq_vendor_status'),  # app-level guard
        Index('ix_subscription_active_unique',
              'vendor_id', 'status', unique=False),
    )
