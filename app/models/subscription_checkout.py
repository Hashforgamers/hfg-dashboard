"""Immutable commercial snapshot for each subscription purchase."""
from app.extension.extensions import db

class SubscriptionCheckout(db.Model):
    __tablename__ = 'subscription_checkouts'
    id = db.Column(db.String(36), primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'))
    order_id = db.Column(db.String(80), unique=True)
    payment_id = db.Column(db.String(80), unique=True)
    state = db.Column(db.String(24), nullable=False, default='preview')
    snapshot = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    paid_at = db.Column(db.DateTime(timezone=True))
