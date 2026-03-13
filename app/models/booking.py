# models/booking.py
from sqlalchemy import Column, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.extension.extensions import db

from .availableGame import AvailableGame
from .slot import Slot

class Booking(db.Model):
    __tablename__ = 'bookings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    game_id = Column(Integer, ForeignKey('available_games.id'), nullable=False)
    slot_id = Column(Integer, ForeignKey('slots.id'), nullable=False)
    status = db.Column(db.String(20), default='pending_verified')  # New field for verification status
    squad_details = Column(JSON, nullable=True)
    
    booking_extra_services = relationship('BookingExtraService', back_populates='booking', cascade='all, delete-orphan')
    squad_members = relationship('BookingSquadMember', back_populates='booking', cascade='all, delete-orphan')

    # Relationship with AvailableGame (many-to-one)
    game = relationship('AvailableGame', back_populates='bookings')

    # Relationship with Slot (many-to-one)
    slot = relationship('Slot', back_populates='bookings')


# Ensure BookingSquadMember mapper is registered before first query-time mapper configure.
from .bookingSquadMember import BookingSquadMember  # noqa: E402,F401
