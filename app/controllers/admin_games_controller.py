# app/controllers/admin_games_controller.py (or add to vendor_games_controller.py)
from flask import Blueprint, jsonify, request
from app.services.game_service import GameService
from app.models.game import Game
from app.extension.extensions import db

admin_games_bp = Blueprint('admin_games', __name__)


@admin_games_bp.route('/games', methods=['POST'])
def create_game():
    """Create a new game with optional image"""
    data = request.form  # Using form data because of file upload
    
    # Create game first
    game = Game(
        name=data.get('name'),
        description=data.get('description'),
        genre=data.get('genre'),
        platform=data.get('platform'),
        esrb_rating=data.get('esrb_rating'),
        multiplayer=data.get('multiplayer', 'false').lower() == 'true',
        trailer_url=data.get('trailer_url')
    )
    
    db.session.add(game)
    db.session.commit()
    
    # Upload image if provided
    if 'image' in request.files:
        image_file = request.files['image']
        result = GameService.update_game_image(game.id, image_file)
        if not result['success']:
            return jsonify({'error': f"Game created but image upload failed: {result['error']}"}), 207
    
    return jsonify({
        'message': 'Game created successfully',
        'game': game.to_dict()
    }), 201


@admin_games_bp.route('/games/<int:game_id>', methods=['PUT'])
def update_game(game_id):
    """Update game details"""
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    data = request.form
    
    # Update fields
    if 'name' in data:
        game.name = data['name']
    if 'description' in data:
        game.description = data['description']
    if 'genre' in data:
        game.genre = data['genre']
    if 'platform' in data:
        game.platform = data['platform']
    
    # Upload new image if provided
    if 'image' in request.files:
        image_file = request.files['image']
        result = GameService.update_game_image(game.id, image_file)
        if not result['success']:
            return jsonify({'error': result['error']}), 400
    
    db.session.commit()
    return jsonify({
        'message': 'Game updated successfully',
        'game': game.to_dict()
    }), 200
