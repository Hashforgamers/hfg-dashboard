# models/userPass.py
from sqlalchemy import Column, Integer, Date, ForeignKey, DateTime, Boolean, String, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.extension.extensions import db
import secrets
import string

class UserPass(db.Model):
    __tablename__ = 'user_passes'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    cafe_pass_id = Column(Integer, ForeignKey('cafe_passes.id'), nullable=False, index=True)
    purchased_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True, index=True)
    
    # Date-based pass fields
    valid_from = Column(Date, nullable=True)
    valid_to = Column(Date, nullable=True)
    
    # Hour-based pass fields (NEW)
    pass_mode = Column(String(20), nullable=False, default='date_based', index=True)
    pass_uid = Column(String(20), unique=True, nullable=True, index=True)
    total_hours = Column(Numeric(precision=10, scale=2), nullable=True)
    remaining_hours = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # Relationships - FIXED: Use string reference for lazy loading
    cafe_pass = relationship('CafePass', backref='user_passes')
    
    # FIXED: Use string reference instead of direct class import
    redemption_logs = relationship(
        'PassRedemptionLog',  # String reference, not class
        back_populates='user_pass',
        cascade='all, delete-orphan',
        lazy='dynamic'  # Use dynamic loading to avoid circular dependency
    )
    
    def __repr__(self):
        return f"<UserPass id={self.id} user_id={self.user_id} mode={self.pass_mode} uid={self.pass_uid}>"
    
    @staticmethod
    def generate_pass_uid(length=12):
        """Generate unique pass UID for hour-based passes"""
        chars = string.ascii_uppercase + string.digits
        return 'HFG-' + ''.join(secrets.choice(chars) for _ in range(length))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'cafe_pass_id': self.cafe_pass_id,
            'cafe_pass_name': self.cafe_pass.name if self.cafe_pass else None,
            'vendor_id': self.cafe_pass.vendor_id if self.cafe_pass else None,
            'purchased_at': self.purchased_at.isoformat() if self.purchased_at else None,
            'is_active': self.is_active,
            'pass_mode': self.pass_mode,
            'valid_from': self.valid_from.isoformat() if self.valid_from else None,
            'valid_to': self.valid_to.isoformat() if self.valid_to else None,
            'pass_uid': self.pass_uid,
            'total_hours': float(self.total_hours) if self.total_hours else None,
            'remaining_hours': float(self.remaining_hours) if self.remaining_hours else None,
        }
