from sqlalchemy.orm import Session
from app.models.game import Game
from app.models.vendorGame import VendorGame
from app.extension.extensions import db

class GameService:
    @staticmethod
    def get_all_games():
        return Game.query.all()

    @staticmethod
    def get_vendor_games(vendor_id: int):
        return db.session.query(VendorGame, Game).\
            join(Game).\
            filter(VendorGame.vendor_id == vendor_id, VendorGame.is_available == True).all()

    @staticmethod
    def add_game_to_vendor(vendor_id: int, game_id: int, price_per_hour: float):
        existing = VendorGame.query.filter_by(vendor_id=vendor_id, game_id=game_id).first()
        if not existing:
            vendor_game = VendorGame(vendor_id=vendor_id, game_id=game_id, price_per_hour=price_per_hour)
            db.session.add(vendor_game)
            db.session.commit()
        return existing
