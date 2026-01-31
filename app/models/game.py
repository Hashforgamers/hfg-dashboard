# app/models/game.py
from sqlalchemy import Column, Integer, String, Text, Float, Date, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.extension.extensions import db
from datetime import datetime


class Game(db.Model):
    __tablename__ = 'games'

    id = Column(Integer, primary_key=True)
    slug = Column(String(255), unique=True, index=True)  # ✅ NEW
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    genre = Column(String(100))
    platform = Column(String(50))
    release_date = Column(Date)
    average_rating = Column(Float, default=0.0)
    esrb_rating = Column(String(50))
    multiplayer = Column(Boolean, default=False)
    
    # ✅ This will store RAWG background_image URL automatically!
    image_url = Column(String(500))
    cloudinary_public_id = Column(String(255))
    trailer_url = Column(String(500))
    
    # ✅ NEW - RAWG metadata
    rawg_rating = Column(Float)
    metacritic = Column(Integer)
    playtime = Column(Integer)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_synced = Column(DateTime)  # ✅ NEW

    vendor_games = relationship('VendorGame', back_populates='game', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'name': self.name,
            'description': self.description,
            'genre': self.genre,
            'platform': self.platform,
            'release_date': self.release_date.isoformat() if self.release_date else None,
            'average_rating': self.average_rating,
            'rawg_rating': self.rawg_rating,
            'metacritic': self.metacritic,
            'playtime': self.playtime,
            'esrb_rating': self.esrb_rating,
            'multiplayer': self.multiplayer,
            'image_url': self.image_url,  # ✅ RAWG background_image goes here!
            'trailer_url': self.trailer_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_synced': self.last_synced.isoformat() if self.last_synced else None
        }
    
    @classmethod
    def from_rawg_api(cls, rawg_data):
        """Create Game from RAWG API - image_url gets background_image automatically!"""
        from datetime import datetime
        
        # Extract genre
        genre = None
        if rawg_data.get('genres') and len(rawg_data['genres']) > 0:
            genre = rawg_data['genres'][0]['name']
        
        # Extract platform
        platform = None
        if rawg_data.get('platforms') and len(rawg_data['platforms']) > 0:
            platform = rawg_data['platforms'][0]['platform']['name']
        
        # Check multiplayer
        multiplayer = False
        if rawg_data.get('tags'):
            multiplayer = any(tag['name'].lower() in ['multiplayer', 'co-op', 'online co-op'] 
                            for tag in rawg_data['tags'])
        
        # ESRB rating
        esrb_rating = None
        if rawg_data.get('esrb_rating'):
            esrb_rating = rawg_data['esrb_rating'].get('name')
        
        # Parse release date
        release_date = None
        if rawg_data.get('released'):
            try:
                release_date = datetime.strptime(rawg_data['released'], '%Y-%m-%d').date()
            except:
                pass
        
        return cls(
            id=rawg_data['id'],
            slug=rawg_data['slug'],
            name=rawg_data['name'],
            description=rawg_data.get('description_raw'),
            genre=genre,
            platform=platform,
            release_date=release_date,
            average_rating=rawg_data.get('rating', 0.0),
            rawg_rating=rawg_data.get('rating'),
            metacritic=rawg_data.get('metacritic'),
            playtime=rawg_data.get('playtime'),
            esrb_rating=esrb_rating,
            multiplayer=multiplayer,
            image_url=rawg_data.get('background_image'),  # ✅✅ RAWG IMAGE HERE!
            last_synced=datetime.utcnow()
        )

    def __repr__(self):
        return f"<Game {self.name} ({self.platform})>"
