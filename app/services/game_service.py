from sqlalchemy.orm import Session
from app.models.game import Game
from app.models.vendorGame import VendorGame
from app.extension.extensions import db
from app.services.cloudinary_game_service import CloudinaryGameImageService


class GameService:
    @staticmethod
    def get_all_games():
        return Game.query.all()

    @staticmethod
    def get_vendor_games(vendor_id: int):
        """Get all games for a vendor"""
        return db.session.query(VendorGame, Game).\
            join(Game, VendorGame.game_id == Game.id).\
            filter(VendorGame.vendor_id == vendor_id, VendorGame.is_available == True).all()

    @staticmethod
    def add_game_to_vendor(vendor_id: int, game_id: int, console_type: str, price_per_hour: float, max_slots: int = 1):
        """Add a game to vendor with specific console type"""
        # Validate console type
        valid_consoles = ['pc', 'ps5', 'xbox']
        if console_type.lower() not in valid_consoles:
            raise ValueError(f"Invalid console type. Must be one of: {', '.join(valid_consoles)}")
        
        existing = VendorGame.query.filter_by(
            vendor_id=vendor_id, 
            game_id=game_id, 
            console_type=console_type.lower()
        ).first()
        
        if existing:
            raise ValueError(f"Game already exists for this console type")
        
        vendor_game = VendorGame(
            vendor_id=vendor_id, 
            game_id=game_id, 
            console_type=console_type.lower(),
            price_per_hour=price_per_hour,
            max_slots=max_slots
        )
        db.session.add(vendor_game)
        db.session.commit()
        return vendor_game

    @staticmethod
    def update_game_image(game_id: int, image_file):
        """Update game cover image using Cloudinary"""
        game = Game.query.get(game_id)
        if not game:
            return {'success': False, 'error': 'Game not found'}

        # Delete old image if exists
        if game.cloudinary_public_id:
            CloudinaryGameImageService.delete_game_image(game.cloudinary_public_id)

        # Upload new image
        upload_result = CloudinaryGameImageService.upload_game_cover_image(
            image_file, 
            game.id, 
            game.name
        )

        if upload_result['success']:
            game.image_url = upload_result['url']
            game.cloudinary_public_id = upload_result['public_id']
            db.session.commit()
            return {
                'success': True, 
                'image_url': game.image_url,
                'public_id': game.cloudinary_public_id
            }
        
        return upload_result

    @staticmethod
    def delete_game_image(game_id: int):
        """Delete game cover image"""
        game = Game.query.get(game_id)
        if not game:
            return {'success': False, 'error': 'Game not found'}

        if game.cloudinary_public_id:
            result = CloudinaryGameImageService.delete_game_image(game.cloudinary_public_id)
            if result['success']:
                game.image_url = None
                game.cloudinary_public_id = None
                db.session.commit()
            return result
        
        return {'success': False, 'error': 'No image to delete'}
