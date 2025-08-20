from sqlalchemy import Column, Integer, String, Boolean, DateTime, DECIMAL, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text
from app.extension.extensions import db

class BankTransferDetails(db.Model):
    __tablename__ = 'bank_transfer_details'
    
    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), unique=True, nullable=False)
    account_holder_name = Column(String(100), nullable=True)  # Made nullable
    bank_name = Column(String(100), nullable=True)           # Made nullable
    account_number = Column(String(30), nullable=True)       # Made nullable
    ifsc_code = Column(String(15), nullable=True)            # Made nullable
    upi_id = Column(String(100), nullable=True)
    is_verified = Column(Boolean, default=False)
    verification_status = Column(String(10), default='PENDING')
    
    # IST Timestamp columns
    created_at = Column(
        DateTime(timezone=True),
        server_default=text("TIMEZONE('Asia/Kolkata', now())"),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=text("TIMEZONE('Asia/Kolkata', now())"),
        nullable=False
    )
    
    # Relationships
    vendor = relationship('Vendor', back_populates='bank_details', uselist=False)
    
    def get_masked_account_number(self):
        """Return masked account number for UI display"""
        if not self.account_number or len(self.account_number) <= 4:
            return self.account_number
        return 'X' * (len(self.account_number) - 4) + self.account_number[-4:]
    
    def get_masked_upi_id(self):
        """Return masked UPI ID for UI display (mask first 4 characters)"""
        if not self.upi_id or len(self.upi_id) <= 4:
            return '****'
        return '****' + self.upi_id[4:]
    
    def __str__(self):
        return f"BankDetails(vendor_id={self.vendor_id}, holder={self.account_holder_name})"

class PayoutTransaction(db.Model):
    __tablename__ = 'payout_transactions'
    
    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    transfer_mode = Column(String(10), nullable=False)  # 'BANK' or 'UPI'
    utr_number = Column(String(100), nullable=True)
    payout_date = Column(
        DateTime(timezone=True),
        server_default=text("TIMEZONE('Asia/Kolkata', now())")
    )
    status = Column(String(10), default='PENDING', nullable=False)  # 'PENDING', 'SUCCESS', 'FAILED'
    remarks = Column(Text, nullable=True)
    
    # IST Timestamp columns
    created_at = Column(
        DateTime(timezone=True),
        server_default=text("TIMEZONE('Asia/Kolkata', now())"),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=text("TIMEZONE('Asia/Kolkata', now())"),
        nullable=False
    )
    
    # Relationships
    vendor = relationship('Vendor', back_populates='payouts')
    
    def __str__(self):
        return f"Payout(vendor_id={self.vendor_id}, amount={self.amount}, status={self.status})"
