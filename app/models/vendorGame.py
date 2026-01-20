from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.extension.extensions import db

class VendorGame(db.Model):
    __tablename__ = 'vendor_games'

    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False, index=True)
    price_per_hour = Column(Float, default=0.0)  # Vendor-specific pricing
    is_available = Column(Boolean, default=True)
    max_slots = Column(Integer, default=1)  # Capacity for this game/platform

    vendor = relationship('Vendor', back_populates='vendor_games')
    game = relationship('Game', back_populates='vendor_games')

    __table_args__ = (db.UniqueConstraint('vendor_id', 'game_id', name='unique_vendor_game'),)

    def __repr__(self):
        return f'<VendorGame vendor={self.vendor_id} game={self.game_id}>'
