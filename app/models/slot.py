# models/slot.py
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Date, Time
from sqlalchemy.orm import relationship
from app.extension.extensions import db


class Slot(db.Model):
    __tablename__ = 'slots'

    id = db.Column(db.Integer, primary_key=True)
    gaming_type_id = Column(Integer, nullable=False)
    start_time = db.Column(Time, nullable=False)
    end_time = db.Column(Time, nullable=False)
    available_slot = Column(Integer, nullable=False)
    is_available = db.Column(Boolean, default=True)

    # Relationship with Booking (one-to-many)
    bookings = relationship('Booking', back_populates='slot', cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Slot available_game_id={self.gaming_type_id} time_bracket={self.start_time} - {self.end_time}>"

