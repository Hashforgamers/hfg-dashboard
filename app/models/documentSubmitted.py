from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.extension.extensions import db

class DocumentSubmitted(db.Model):
    __tablename__ = 'documents_submitted'
    
    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False)
    document_name = Column(String(50), nullable=False)
    submitted = Column(Boolean, default=False)

    vendor = relationship('Vendor', back_populates='documents_submitted')
    
