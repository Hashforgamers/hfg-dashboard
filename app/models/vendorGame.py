from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.extension.extensions import db


class VendorGame(db.Model):
    __tablename__ = 'vendor_games'

    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False, index=True)
    console_id = Column(Integer, ForeignKey('consoles.id'), nullable=False, index=True)
    is_available = Column(Boolean, default=True)

    vendor = relationship('Vendor', back_populates='vendor_games')
    game = relationship('Game', back_populates='vendor_games')
    console = relationship('Console')

    __table_args__ = (db.UniqueConstraint('vendor_id', 'game_id', 'console_id', name='unique_vendor_game_console'),)

    @property
    def price_per_hour(self):
        """
        Dynamically compute price from parent AvailableGame.
        - If an active ConsolePricingOffer exists for the console's platform → return offered_price
        - Else → return AvailableGame.single_slot_price
        """
        try:
            # Step 1: Find the AvailableGame linked to this console
            # Console → AvailableGame via available_game_console association
            console = self.console
            if not console:
                return 0.0

            # Find AvailableGame that has this console linked
            from app.models.availableGame import AvailableGame
            from app.models.consolePricingOffer import ConsolePricingOffer

            available_game = AvailableGame.query.filter(
                AvailableGame.vendor_id == self.vendor_id,
                AvailableGame.consoles.any(id=console.id)
            ).first()

            if not available_game:
                return 0.0

            # Step 2: Check for any currently active offer on this AvailableGame
            active_offers = ConsolePricingOffer.query.filter_by(
                vendor_id=self.vendor_id,
                available_game_id=available_game.id,
                is_active=True
            ).all()

            current_offer = next(
                (offer for offer in active_offers if offer.is_currently_active()),
                None
            )

            # Step 3: Return offer price or default price
            if current_offer:
                return float(current_offer.offered_price)

            return float(available_game.single_slot_price)

        except Exception:
            return 0.0

    @property
    def effective_price_info(self):
        """
        Returns full pricing context: base price, offer price, offer details.
        Useful for API responses that need to show discount info.
        """
        try:
            from app.models.availableGame import AvailableGame
            from app.models.consolePricingOffer import ConsolePricingOffer

            console = self.console
            if not console:
                return {'price': 0.0, 'is_offer': False, 'default_price': 0.0}

            available_game = AvailableGame.query.filter(
                AvailableGame.vendor_id == self.vendor_id,
                AvailableGame.consoles.any(id=console.id)
            ).first()

            if not available_game:
                return {'price': 0.0, 'is_offer': False, 'default_price': 0.0}

            default_price = float(available_game.single_slot_price)

            active_offers = ConsolePricingOffer.query.filter_by(
                vendor_id=self.vendor_id,
                available_game_id=available_game.id,
                is_active=True
            ).all()

            current_offer = next(
                (offer for offer in active_offers if offer.is_currently_active()),
                None
            )

            if current_offer:
                return {
                    'price': float(current_offer.offered_price),
                    'is_offer': True,
                    'default_price': default_price,
                    'offer_name': current_offer.offer_name,
                    'offer_id': current_offer.id,
                    'discount_percentage': current_offer.get_discount_percentage(),
                    'valid_until': f"{current_offer.end_date} {current_offer.end_time.strftime('%H:%M')}"
                }

            return {
                'price': default_price,
                'is_offer': False,
                'default_price': default_price
            }

        except Exception:
            return {'price': 0.0, 'is_offer': False, 'default_price': 0.0}

    def to_dict(self):
        """Serialize VendorGame — price is always dynamically computed"""
        price_info = self.effective_price_info
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'game_id': self.game_id,
            'console_id': self.console_id,
            'is_available': self.is_available,
            'price_per_hour': price_info['price'],
            'is_offer': price_info.get('is_offer', False),
            'default_price': price_info.get('default_price', 0.0),
            'offer_name': price_info.get('offer_name'),
            'offer_id': price_info.get('offer_id'),
            'discount_percentage': price_info.get('discount_percentage'),
            'valid_until': price_info.get('valid_until'),
        }

    def __repr__(self):
        return f'<VendorGame vendor={self.vendor_id} game={self.game_id} console={self.console_id}>'
