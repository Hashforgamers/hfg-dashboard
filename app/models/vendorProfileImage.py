from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.extension.extensions import db
from datetime import datetime

class VendorProfileImage(db.Model):
    __tablename__ = 'vendor_profile_images'
    
    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), unique=True, nullable=False)
    image_url = Column(Text, nullable=False)
    public_id = Column(String(255), nullable=True)  # Cloudinary public_id for deletion
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    # One-to-One relationship back to Vendor
    vendor = relationship('Vendor', back_populates='profile_image', uselist=False)
    
    def __str__(self):
        return f"VendorProfileImage(id={self.id}, vendor_id={self.vendor_id})"
    
    def __repr__(self):
        return self.__str__()
