from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.extension.extensions import db

class PhysicalAddress(db.Model):
    __tablename__ = 'physical_address'

    id = Column(Integer, primary_key=True)
    address_type = Column(String(50), nullable=False)
    addressLine1 = Column(String(255), nullable=False)
    addressLine2 = Column(String(255), nullable=True)
    pincode = Column(String(10), nullable=False)
    state = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    latitude = Column(String(20))
    longitude = Column(String(20))

    # Foreign Key to Vendor
    parent_id = Column(Integer, ForeignKey('vendors.id'), nullable=False)
    parent_type = Column(String(50), nullable=False, default='vendor')  # 'vendor' to be used here

    # Relationship to Vendor
    vendor = relationship(
        'Vendor',
        back_populates='physical_address',
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True  # Ensure only one PhysicalAddress can be linked to a Vendor at a time
    )

    def __str__(self):
        return f"PhysicalAddress(id={self.id}, addressLine1='{self.addressLine1}', addressLine2='{self.addressLine2}')"
