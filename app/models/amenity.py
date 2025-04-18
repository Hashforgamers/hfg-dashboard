from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.extension.extensions import db

class Amenity(db.Model):
    __tablename__ = 'amenities'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    available = Column(Boolean, default=False)
    
    # Foreign key to link back to Vendor
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False)

    # Define the relationship back to Vendor
    vendors = relationship('Vendor', back_populates='amenities')
