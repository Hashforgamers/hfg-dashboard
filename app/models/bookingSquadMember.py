from sqlalchemy import Column, Integer, ForeignKey, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.extension.extensions import db


class BookingSquadMember(db.Model):
    __tablename__ = "booking_squad_members"

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    member_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    member_position = Column(Integer, nullable=False)
    is_captain = Column(Boolean, nullable=False, default=False)
    name_snapshot = Column(String(255), nullable=False)
    phone_snapshot = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    booking = relationship("Booking", back_populates="squad_members")
