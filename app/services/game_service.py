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
        """Search games by name (case-insensitive, partial match)"""
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
    def get_vendor_games_grouped(vendor_id: int):
        """
        Get all vendor games grouped by game
        Returns dict with game as key and list of consoles as value
        """
        vendor_games = VendorGame.query.filter_by(
            vendor_id=vendor_id,
            is_available=True
        ).all()
        
        games_dict = {}
        for vg in vendor_games:
            game_id = vg.game_id
            if game_id not in games_dict:
                games_dict[game_id] = {
                    'game': vg.game,
                    'consoles': []
                }
            
            games_dict[game_id]['consoles'].append({
                'console': vg.console,
                'vendor_game_id': vg.id,
                'price_per_hour': vg.price_per_hour
            })
        
        return games_dict

    @staticmethod
    def get_consoles_by_platform(vendor_id: int, platform_type: str):
        """Get all consoles for a specific platform (PC, PS5, Xbox, VR)"""
        available_game = AvailableGame.query.filter_by(
            vendor_id=vendor_id,
            game_name=platform_type.upper()
        ).first()
        
        if not available_game:
            return []
        
        return available_game.consoles

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
