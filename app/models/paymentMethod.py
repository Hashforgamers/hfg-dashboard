from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.extension.extensions import db
from datetime import datetime
from app.models.paymentVendorMap import PaymentVendorMap

class PaymentMethod(db.Model):
    __tablename__ = 'payment_method'
    
    pay_method_id = Column(Integer, primary_key=True)
    method_name = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to PaymentVendorMap
    vendor_maps = relationship('PaymentVendorMap', back_populates='payment_method', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<PaymentMethod {self.method_name}>'
    
    def to_dict(self):
        return {
            'pay_method_id': self.pay_method_id,
            'method_name': self.method_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
