from sqlalchemy import Column, Integer, ForeignKey, String, Float, Date, Time
from sqlalchemy.orm import relationship
from datetime import datetime
from app.extension.extensions import db

class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, nullable=False)
    vendor_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    booked_date = Column(Date, default=datetime.utcnow().date(), nullable=False)
    booking_date = Column(Date, default=datetime.utcnow().date(), nullable=False)
    booking_time = Column(Time, default=datetime.utcnow().time(), nullable=False)
    user_name = Column(String(255), nullable=False)
    original_amount = Column(Float, nullable=False)
    discounted_amount = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    mode_of_payment = Column(String(50), default='online', nullable=False)
    booking_type = Column(String(255), default='hash', nullable=False)
    settlement_status = Column(String(50), default='pending', nullable=False)

    def __repr__(self):
        return f"<Transaction user={self.user_name} amount={self.amount} status={self.settlement_status}>"
