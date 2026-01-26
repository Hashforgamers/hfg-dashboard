# scripts/add_game_images.py
"""
Script to add images to existing games
Usage: python scripts/add_game_images.py
"""

from app import create_app
from app.models.game import Game
from app.services.cloudinary_game_service import CloudinaryGameImageService
from app.extension.extensions import db

app = create_app()

def add_images_to_games():
    with app.app_context():
        games = Game.query.all()
        
        for game in games:
            # Skip if already has image
            if game.image_url:
                print(f"✓ {game.name} already has an image")
                continue
            
            print(f"\n📷 Add image for: {game.name}")
            image_path = input("Enter image file path (or 'skip'): ")
            
            if image_path.lower() == 'skip':
                continue
            
            try:
                with open(image_path, 'rb') as image_file:
                    result = CloudinaryGameImageService.upload_game_cover_image(
                        image_file,
                        game.id,
                        game.name
                    )
                    
                    if result['success']:
                        game.image_url = result['url']
                        game.cloudinary_public_id = result['public_id']
                        db.session.commit()
                        print(f"✅ Image uploaded for {game.name}")
                    else:
                        print(f"❌ Failed: {result['error']}")
            except Exception as e:
                print(f"❌ Error: {str(e)}")

if __name__ == '__main__':
    add_images_to_games()
