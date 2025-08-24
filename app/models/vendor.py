from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship, foreign
from app.extension.extensions import db
from datetime import datetime
from app.models.documentSubmitted import DocumentSubmitted
from app.models.openingDay import OpeningDay
from app.models.availableGame import AvailableGame
from app.models.vendorProfileImage import VendorProfileImage
from app.models.contactInfo import ContactInfo
from app.models.businessRegistration import BusinessRegistration
from app.models.timing import Timing
from app.models.amenity import Amenity
from app.models.physicalAddress import PhysicalAddress
from app.models.document import Document
from app.models.bankTransferDetails import BankTransferDetails, PayoutTransaction
from app.models.paymentVendorMap import PaymentVendorMap
from app.models.paymentMethod import PaymentMethod
from sqlalchemy.sql import and_
from app.models.vendorAccount import VendorAccount
from app.models.website import Website

class Vendor(db.Model):
    __tablename__ = 'vendors'
    
    id = Column(Integer, primary_key=True)
    cafe_name = Column(String(255), nullable=False)
    owner_name = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True)

    # Foreign Key to BusinessRegistration
    business_registration_id = Column(Integer, ForeignKey('business_registration.id'), nullable=True)
    # Foreign Key to Timing
    timing_id = Column(Integer, ForeignKey('timing.id'), nullable=False)
    
    profile_image = relationship(
        'VendorProfileImage', 
        back_populates='vendor', 
        uselist=False, 
        cascade='all, delete-orphan'
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    physical_address = relationship(
        'PhysicalAddress',
        primaryjoin="and_(foreign(PhysicalAddress.parent_id) == Vendor.id, PhysicalAddress.parent_type == 'vendor')",
        back_populates='vendor',
        uselist=False,
        cascade="all, delete-orphan"
    )
    
       # WEBSITE RELATIONSHIP - One-to-One
    website = relationship(
        'Website', 
        back_populates='vendor', 
        uselist=False, 
        cascade='all, delete-orphan'
    )
    
       # Bank transfer details relationship
    bank_details = relationship(
        'BankTransferDetails', 
        back_populates='vendor', 
        uselist=False, 
        cascade='all, delete-orphan'
    )

    # Payout transactions relationship
    payouts = relationship(
        'PayoutTransaction', 
        back_populates='vendor', 
        cascade='all, delete-orphan'
    )


    # Relationship to ContactInfo
    # contact_info = relationship("ContactInfo", back_populates="vendor", uselist=False)
    # Relationship to ContactInfo
    # Relationship to ContactInfo
    contact_info = relationship(
        "ContactInfo",
        primaryjoin="and_(foreign(ContactInfo.parent_id) == Vendor.id, ContactInfo.parent_type == 'vendor')",
        back_populates="vendor",
        uselist=False,
        cascade="all, delete-orphan",
        overlaps="contact_info"
    )

    __mapper_args__ = {
        'polymorphic_identity': 'vendor',  # Only 'vendor' here
    }

    # Relationship to BusinessRegistration
    business_registration = relationship('BusinessRegistration', back_populates='vendors')

    # Relationship to Timing
    timing = relationship('Timing', back_populates='vendors', single_parent=True)

    # Relationship to OpeningDay
    opening_days = relationship(
        'OpeningDay',
        back_populates='vendor',
        cascade="all, delete-orphan"
    )
    
    # Add this relationship to your Vendor class
    payment_methods = relationship('PaymentVendorMap', back_populates='vendor', cascade='all, delete-orphan')

    available_games = relationship('AvailableGame', back_populates='vendor', cascade="all, delete-orphan")

    # Relationship to Amenity
    amenities = relationship(
        "Amenity",
        back_populates="vendors",
        cascade="all, delete-orphan"
    )

    # Relationship to DocumentSubmitted
    documents_submitted = relationship(
        'DocumentSubmitted',
        back_populates='vendor',
        cascade="all, delete-orphan"
    )

    # In Vendor model
    account_id = Column(Integer, ForeignKey('vendor_accounts.id'), nullable=True)
    account = relationship('VendorAccount', back_populates='vendors')

    # In vendor.py
    documents = db.relationship("Document", back_populates="vendor", cascade="all, delete-orphan")

    extra_service_categories = relationship('ExtraServiceCategory', back_populates='vendor', cascade='all, delete-orphan')

    # Relationship to Image (new addition)
    images = relationship(
        'Image',
        back_populates='vendor',
        cascade="all, delete-orphan"
    )

       # One-to-One relationship with VendorCredential
    credential = None


    def __str__(self):
        return f"Vendor(id={self.id}, cafe_name='{self.cafe_name}', owner_name='{self.owner_name}', description='{self.description}')"

    def __repr__(self):
        return self.__str__()
