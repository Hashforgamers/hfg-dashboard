from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.extension.extensions import db

class ContactInfo(db.Model):
    __tablename__ = 'contact_info'
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    
    # Polymorphic Foreign Key relationship
    parent_id = Column(Integer, ForeignKey('vendors.id'), nullable=False)  # Define foreign key to Vendor
    parent_type = Column(String(50), nullable=False)

    # Relationship to Vendor
    vendor = relationship(
        "Vendor",  # String reference to Vendor model
        back_populates="contact_info",
        foreign_keys=[parent_id],
        uselist=False
    )
