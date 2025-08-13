from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from app.extension.extensions import db
from sqlalchemy.orm import relationship
from datetime import datetime

class Image(db.Model):
    __tablename__ = 'images'
    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False)
    image_id = Column(String(255), nullable=False) 
    public_id = Column(String(255), nullable=False)          # Cloudinary public_id
    url = Column(String(512), nullable=False)
    path=Column(String(255), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    vendor = relationship('Vendor', back_populates='images')
    
