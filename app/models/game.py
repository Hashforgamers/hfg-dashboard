from sqlalchemy import Column, Integer, String, Text, Float, Date, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.extension.extensions import db
from datetime import datetime


class Game(db.Model):
    __tablename__ = 'games'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    genre = Column(String(100))
    platform = Column(String(50))  # e.g., 'PC', 'PS5', 'Xbox Series X', 'VR'
    release_date = Column(Date)
    average_rating = Column(Float, default=0.0)
    esrb_rating = Column(String(50))
    multiplayer = Column(Boolean, default=False)
    image_url = Column(String(500))
    trailer_url = Column(String(500))

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationship with vendor_games table
    vendor_games = relationship(
        'VendorGame',
        back_populates='game',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Game {self.name} ({self.platform})>"
