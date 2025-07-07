from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.extension.extensions import db
from datetime import datetime

# models/vendorAccount.py
class VendorAccount(db.Model):
    __tablename__ = 'vendor_accounts'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # One-to-many relationship to Vendor
    vendors = relationship(
        'Vendor',
        back_populates='account',
        cascade='all, delete-orphan',
        foreign_keys='Vendor.account_id'  # optional but can solve ambiguous cases
    )
