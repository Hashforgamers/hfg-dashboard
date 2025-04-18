from sqlalchemy import Column, Integer, String, Date
from sqlalchemy.orm import relationship
from app.extension.extensions import db


class BusinessRegistration(db.Model):
    __tablename__ = 'business_registration'
    
    id = Column(Integer, primary_key=True)
    registration_number = Column(String(100), nullable=False)
    registration_date = Column(Date, nullable=False)

    vendors = relationship('Vendor', back_populates='business_registration')
