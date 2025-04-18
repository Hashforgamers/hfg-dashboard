from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.extension.extensions import db

class Timing(db.Model):
    __tablename__ = 'timing'

    id = Column(Integer, primary_key=True)
    opening_time = Column(String(10), nullable=False)
    closing_time = Column(String(10), nullable=False)

    # Relationships
    vendors = relationship('Vendor', back_populates='timing', cascade="all, delete-orphan")
