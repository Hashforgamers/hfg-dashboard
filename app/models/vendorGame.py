from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.extension.extensions import db


class VendorGame(db.Model):
    __tablename__ = 'vendor_games'

    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False, index=True)
    console_id = Column(Integer, ForeignKey('consoles.id'), nullable=False, index=True)  # ✅ NEW - Link to specific console
    price_per_hour = Column(Float, default=0.0)
    is_available = Column(Boolean, default=True)

    vendor = relationship('Vendor', back_populates='vendor_games')
    game = relationship('Game', back_populates='vendor_games')
    console = relationship('Console')  # ✅ NEW - Relationship to Console

    # ✅ UPDATED - One game can only be on one specific console once
    __table_args__ = (db.UniqueConstraint('vendor_id', 'game_id', 'console_id', name='unique_vendor_game_console'),)

    def to_dict(self):
        """Serialize VendorGame model to dictionary"""
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'game_id': self.game_id,
            'console_id': self.console_id,  # ✅ NEW
            'price_per_hour': self.price_per_hour,
            'is_available': self.is_available,
        }

    def __repr__(self):
        return f'<VendorGame vendor={self.vendor_id} game={self.game_id} console={self.console_id}>'
