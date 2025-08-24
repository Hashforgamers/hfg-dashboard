from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from app.extension.extensions import db
from datetime import datetime



class PaymentVendorMap(db.Model):
    __tablename__ = 'payment_vendor_map'
    
    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False)
    pay_method_id = Column(Integer, ForeignKey('payment_method.pay_method_id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vendor = relationship('Vendor', back_populates='payment_methods')
    payment_method = relationship('PaymentMethod', back_populates='vendor_maps')
    
    # Ensure unique mapping between vendor and payment method
    __table_args__ = (
        UniqueConstraint('vendor_id', 'pay_method_id', name='unique_vendor_payment_method'),
    )
    
    def __repr__(self):
        return f'<PaymentVendorMap vendor_id={self.vendor_id} method_id={self.pay_method_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'pay_method_id': self.pay_method_id,
            'method_name': self.payment_method.method_name if self.payment_method else None,
            'vendor_name': self.vendor.cafe_name if self.vendor else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
