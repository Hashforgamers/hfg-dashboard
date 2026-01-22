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
    platform = Column(String(50))
    release_date = Column(Date)
    average_rating = Column(Float, default=0.0)
    esrb_rating = Column(String(50))
    multiplayer = Column(Boolean, default=False)
    image_url = Column(String(500))
    trailer_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    vendor_games = relationship('VendorGame', back_populates='game', cascade='all, delete-orphan')

    def to_dict(self):
        """Serialize Game model to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'genre': self.genre,
            'platform': self.platform,
            'release_date': self.release_date.isoformat() if self.release_date else None,
            'average_rating': self.average_rating,
            'esrb_rating': self.esrb_rating,
            'multiplayer': self.multiplayer,
            'image_url': self.image_url,
            'trailer_url': self.trailer_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<Game {self.name} ({self.platform})>"
