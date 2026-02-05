# app/services/game_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.game import Game
from app.models.vendorGame import VendorGame
from app.models.availableGame import AvailableGame
from app.models.console import Console
from app.extension.extensions import db
from app.services.cloudinary_game_service import CloudinaryGameImageService
from datetime import datetime


class GameService:
    @staticmethod
    def get_all_games():
        """Get all games ordered by name"""
        return Game.query.order_by(Game.name.asc()).all()

    @staticmethod
    def search_games(search_term: str):
        """
        Search games by name (case-insensitive, partial match)
        Returns games ordered by relevance
        """
        if not search_term or search_term.strip() == "":
            return GameService.get_all_games()
        
        search_pattern = f"%{search_term}%"
        
        games = Game.query.filter(
            Game.name.ilike(search_pattern)
        ).order_by(
            Game.name.ilike(f"{search_term}%").desc(),
            Game.name.asc()
        ).all()
        
        return games

    @staticmethod
    def get_vendor_games(vendor_id: int):
        """LEGACY: Get all games for a vendor (VendorGame table)"""
        return db.session.query(VendorGame, Game).\
            join(Game, VendorGame.game_id == Game.id).\
            filter(VendorGame.vendor_id == vendor_id, VendorGame.is_available == True).all()

    @staticmethod
    def get_vendor_available_games_with_consoles(vendor_id: int):
        """
        Get all available games for a vendor with console details
        Returns list of dicts with game info and associated consoles
        """
        available_games = AvailableGame.query.filter_by(vendor_id=vendor_id).all()
        
        result = []
        for ag in available_games:
            game = Game.query.filter_by(name=ag.game_name).first()
            
            result.append({
                'available_game_id': ag.id,
                'game_name': ag.game_name,
                'total_slots': ag.total_slot,
                'price_per_slot': ag.single_slot_price,
                'game_details': game.to_dict() if game else None,
                'consoles': [{
                    'id': c.id,
                    'console_number': c.console_number,
                    'console_type': c.console_type,
                    'brand': c.brand
                } for c in ag.consoles]
            })
        
        return result

    @staticmethod
    def add_game_to_vendor(vendor_id: int, game_id: int, console_type: str, price_per_hour: float, max_slots: int = 1):
        """LEGACY: Add a game to vendor with specific console type (VendorGame table)"""
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

        if game.cloudinary_public_id:
            CloudinaryGameImageService.delete_game_image(game.cloudinary_public_id)

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
        """Delete Cloudinary image"""
        game = Game.query.get(game_id)
        if not game:
            return {'success': False, 'error': 'Game not found'}

        if game.cloudinary_public_id:
            result = CloudinaryGameImageService.delete_game_image(game.cloudinary_public_id)
            if result['success']:
                game.cloudinary_public_id = None
                db.session.commit()
            return result
        
        return {'success': False, 'error': 'No Cloudinary image to delete'}
    
    @staticmethod
    def sync_game_from_rawg(rawg_data, update_existing=True):
        """Sync single game from RAWG API"""
        game_id = rawg_data['id']
        existing_game = Game.query.filter_by(id=game_id).first()
        
        if existing_game:
            if update_existing:
                existing_game.slug = rawg_data['slug']
                existing_game.name = rawg_data['name']
                
                if not existing_game.cloudinary_public_id:
                    existing_game.image_url = rawg_data.get('background_image')
                
                if rawg_data.get('genres') and len(rawg_data['genres']) > 0:
                    existing_game.genre = rawg_data['genres'][0]['name']
                
                if rawg_data.get('platforms') and len(rawg_data['platforms']) > 0:
                    existing_game.platform = rawg_data['platforms'][0]['platform']['name']
                
                existing_game.rawg_rating = rawg_data.get('rating')
                existing_game.average_rating = rawg_data.get('rating', 0.0)
                existing_game.metacritic = rawg_data.get('metacritic')
                existing_game.playtime = rawg_data.get('playtime')
                
                if rawg_data.get('esrb_rating'):
                    existing_game.esrb_rating = rawg_data['esrb_rating'].get('name')
                
                if rawg_data.get('tags'):
                    existing_game.multiplayer = any(
                        tag['name'].lower() in ['multiplayer', 'co-op', 'online co-op'] 
                        for tag in rawg_data['tags']
                    )
                
                if rawg_data.get('released'):
                    try:
                        existing_game.release_date = datetime.strptime(
                            rawg_data['released'], '%Y-%m-%d'
                        ).date()
                    except:
                        pass
                
                existing_game.last_synced = datetime.utcnow()
                db.session.commit()
                return (existing_game, False)
            else:
                return (existing_game, False)
        else:
            new_game = Game.from_rawg_api(rawg_data)
            db.session.add(new_game)
            db.session.commit()
            return (new_game, True)
