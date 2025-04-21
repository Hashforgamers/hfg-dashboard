from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, foreign
from app.extension.extensions import db
from sqlalchemy.sql import and_

class ContactInfo(db.Model):
    __tablename__ = 'contact_info'
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)

    parent_id = Column(Integer, nullable=False)
    parent_type = Column(String(50), nullable=False)

    user = relationship(
        "User",  # ← STRING REFERENCE
        primaryjoin="and_(foreign(ContactInfo.parent_id) == User.id, ContactInfo.parent_type == 'user')",
        back_populates="contact_info",
        uselist=False
    )

    vendor = relationship(
        "Vendor",
        primaryjoin="and_(foreign(ContactInfo.parent_id) == Vendor.id, ContactInfo.parent_type == 'vendor')",
        back_populates="contact_info",
        uselist=False
    )
