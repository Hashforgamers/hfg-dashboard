# models/passRedemptionLog.py
from sqlalchemy import Column, Integer, ForeignKey, DateTime, Numeric, String, Boolean, Text, Time
from sqlalchemy.orm import relationship
from datetime import datetime
from app.extension.extensions import db
import pytz

IST = pytz.timezone("Asia/Kolkata")

class PassRedemptionLog(db.Model):
    __tablename__ = 'pass_redemption_logs'
    
    id = Column(Integer, primary_key=True)
    user_pass_id = Column(Integer, ForeignKey('user_passes.id'), nullable=False, index=True)
    booking_id = Column(Integer, ForeignKey('bookings.id'), nullable=True, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    hours_deducted = Column(Numeric(precision=10, scale=2), nullable=False)
    session_start_time = Column(Time, nullable=True)
    session_end_time = Column(Time, nullable=True)
    
    redemption_method = Column(String(20), nullable=False)
    redeemed_by_staff_id = Column(Integer, nullable=True)
    redeemed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(IST), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    
    is_cancelled = Column(Boolean, default=False, nullable=False, index=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships - FIXED: Use string references
    user_pass = relationship('UserPass', back_populates='redemption_logs')
    booking = relationship('Booking', backref='pass_redemptions')
    vendor = relationship('Vendor', foreign_keys=[vendor_id])
    user = relationship('User', foreign_keys=[user_id])
    
    def __repr__(self):
        return f"<PassRedemptionLog id={self.id} pass_id={self.user_pass_id} hours={self.hours_deducted}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_pass_id': self.user_pass_id,
            'booking_id': self.booking_id,
            'vendor_id': self.vendor_id,
            'user_id': self.user_id,
            'hours_deducted': float(self.hours_deducted),
            'session_start_time': self.session_start_time.strftime('%H:%M:%S') if self.session_start_time else None,
            'session_end_time': self.session_end_time.strftime('%H:%M:%S') if self.session_end_time else None,
            'redemption_method': self.redemption_method,
            'redeemed_by_staff_id': self.redeemed_by_staff_id,
            'redeemed_at': self.redeemed_at.isoformat() if self.redeemed_at else None,
            'notes': self.notes,
            'is_cancelled': self.is_cancelled,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
        }
