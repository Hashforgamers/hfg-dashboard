from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from app.extension.extensions import db
from datetime import datetime

class PayAtCafeNotification(db.Model):
    __tablename__ = 'pay_at_cafe_notification'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False)
    booking_id = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=False)  # Amount in paise
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vendor = relationship('Vendor', backref='pay_at_cafe_notifications')
    
    def __repr__(self):
        return f'<PayAtCafeNotification id={self.id} vendor_id={self.vendor_id} amount={self.amount}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'vendor_id': self.vendor_id,
            'booking_id': self.booking_id,
            'amount': self.amount,
            'amount_formatted': f"₹{self.amount / 100:.2f}",
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
