from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.extension.extensions import db

class Website(db.Model):
    __tablename__ = 'website'
    
    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), unique=True, nullable=False)
    url = Column(String(255), nullable=False)

    # Relationship back to Vendor
    vendor = relationship('Vendor', back_populates='website', uselist=False)

    def __str__(self):
        return f"Website(id={self.id}, vendor_id={self.vendor_id}, url='{self.url}')"

    def __repr__(self):
        return self.__str__()
