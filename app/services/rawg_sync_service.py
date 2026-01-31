# app/services/rawg_sync_service.py
import requests
import time
from datetime import datetime
from flask import current_app
from app.extension.extensions import db
from app.models.game import Game
from app.services.game_service import GameService

API_KEY = "5161e75d1d234431ac34d3947d01ea1e"
BASE_URL = "https://api.rawg.io/api/games"


class RAWGSyncService:
    
    @staticmethod
    def fetch_games_page(page=1, page_size=40):
        """Fetch a single page of games from RAWG API"""
        try:
            params = {
                'key': API_KEY,
                'page': page,
                'page_size': page_size
            }
            
            current_app.logger.info(f"Fetching RAWG page {page}...")
            response = requests.get(BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data
            
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error fetching RAWG page {page}: {e}")
            return None
    
    @staticmethod
    def sync_games(max_pages=10, update_existing=True):
        """Sync games from RAWG API"""
        added_count = 0
        updated_count = 0
        error_count = 0
        total_processed = 0
        
        current_app.logger.info(f"🚀 Starting RAWG sync (max_pages={max_pages})...")
        
        for page in range(1, max_pages + 1):
            data = RAWGSyncService.fetch_games_page(page)
            
            if not data or 'results' not in data:
                current_app.logger.warning(f"No data for page {page}")
                break
            
            games = data['results']
            current_app.logger.info(f"📦 Page {page}: {len(games)} games")
            
            for game_data in games:
                try:
                    game, was_created = GameService.sync_game_from_rawg(
                        game_data, 
                        update_existing=update_existing
                    )
                    
                    if was_created:
                        added_count += 1
                    else:
                        if update_existing:
                            updated_count += 1
                    
                    total_processed += 1
                    
                except Exception as e:
                    error_count += 1
                    current_app.logger.error(
                        f"❌ Error syncing game {game_data.get('name', 'Unknown')}: {e}"
                    )
            
            db.session.commit()
            current_app.logger.info(
                f"💾 Page {page} committed: {added_count} added, {updated_count} updated"
            )
            
            if not data.get('next'):
                current_app.logger.info("No more pages available")
                break
            
            time.sleep(1)  # Rate limiting
        
        result = {
            'added': added_count,
            'updated': updated_count,
            'errors': error_count,
            'total': total_processed
        }
        
        current_app.logger.info(f"""
        ✅ RAWG Sync Complete!
        - Added: {added_count}
        - Updated: {updated_count}
        - Errors: {error_count}
        - Total: {total_processed}
        """)
        
        return result
