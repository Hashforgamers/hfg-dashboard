# app/models/vendor_day_slot_config.py

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from app.extension.extensions import db

class VendorDaySlotConfig(db.Model):
    __tablename__ = 'vendor_day_slot_config'

    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False)
    day = Column(String(3), nullable=False)  # 'mon'...'sun'
    opening_time = Column(String(10), nullable=False)  # e.g., "09:00 AM" or "09:00"
    closing_time = Column(String(10), nullable=False)  # e.g., "11:00 PM" or "23:00"
    slot_duration = Column(Integer, nullable=False)    # minutes

    __table_args__ = (
        UniqueConstraint('vendor_id', 'day', name='uq_vendor_day'),
    )

    def __repr__(self):
        return f"<VendorDaySlotConfig vendor_id={self.vendor_id} day={self.day} {self.opening_time}-{self.closing_time} dur={self.slot_duration}m>"
