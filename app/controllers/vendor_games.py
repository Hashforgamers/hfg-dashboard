from flask import Blueprint, jsonify, request
from app.services.game_service import GameService
from app.models.game import Game
from app.models.vendorGame import VendorGame
from app.extension.extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity


vendor_games_bp = Blueprint('vendor_games', __name__)


@vendor_games_bp.route('/games', methods=['GET'])
def get_all_games():
    """
    Fetch all available games with optional search
    Query params:
        - search: Search term for filtering games by name
    Example: /games?search=gta
    """
    search = request.args.get('search', '').strip()
    
    if search:
        # Search by name (case-insensitive, partial match)
        games = GameService.search_games(search)
    else:
        # Get all games
        games = GameService.get_all_games()
    
    return jsonify([game.to_dict() for game in games])


@vendor_games_bp.route('/vendor/<int:vendor_id>/games', methods=['GET'])
def list_vendor_games(vendor_id):
    """
    List all games for a specific vendor
    Returns games with their vendor-specific configuration (console, price, etc.)
    """
    games = GameService.get_vendor_games(vendor_id)
    return jsonify([{
        'vendor_game': vg.to_dict(), 
        'game': g.to_dict()
    } for vg, g in games])


@vendor_games_bp.route('/vendor/<int:vendor_id>/games/<int:game_id>', methods=['POST'])
def add_vendor_game(vendor_id, game_id):
    """
    Add a game to vendor with console type specification
    
    Request body:
    {
        "console_type": "pc" | "ps5" | "xbox",
        "price_per_hour": 50.0,
        "max_slots": 1
    }
    """
    data = request.json
    console_type = data.get('console_type')
    price = data.get('price_per_hour', 50.0)
    max_slots = data.get('max_slots', 1)
    
    # Validation
    if not console_type:
        return jsonify({'error': 'console_type is required'}), 400
    
    if price <= 0:
        return jsonify({'error': 'price_per_hour must be greater than 0'}), 400
    
    if max_slots < 1:
        return jsonify({'error': 'max_slots must be at least 1'}), 400
    
    try:
        result = GameService.add_game_to_vendor(vendor_id, game_id, console_type, price, max_slots)
        return jsonify({
            'message': 'Game added successfully',
            'vendor_game': result.to_dict()
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to add game'}), 500


@vendor_games_bp.route('/vendor/<int:vendor_id>/games/<int:vendor_game_id>', methods=['PUT'])
def update_vendor_game(vendor_id, vendor_game_id):
    """
    Update vendor game configuration
    
    Request body:
    {
        "price_per_hour": 60.0,
        "max_slots": 2,
        "is_available": true
    }
    """
    data = request.json
    
    try:
        vendor_game = VendorGame.query.filter_by(
            id=vendor_game_id,
            vendor_id=vendor_id
        ).first()
        
        if not vendor_game:
            return jsonify({'error': 'Vendor game not found'}), 404
        
        # Update fields if provided
        if 'price_per_hour' in data:
            vendor_game.price_per_hour = data['price_per_hour']
        
        if 'max_slots' in data:
            vendor_game.max_slots = data['max_slots']
        
        if 'is_available' in data:
            vendor_game.is_available = data['is_available']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Game updated successfully',
            'vendor_game': vendor_game.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to update game'}), 500


@vendor_games_bp.route('/vendor/<int:vendor_id>/games/<int:vendor_game_id>', methods=['DELETE'])
def remove_vendor_game(vendor_id, vendor_game_id):
    """
    Remove a game from vendor
    """
    try:
        vendor_game = VendorGame.query.filter_by(
            id=vendor_game_id,
            vendor_id=vendor_id
        ).first()
        
        if not vendor_game:
            return jsonify({'error': 'Vendor game not found'}), 404
        
        db.session.delete(vendor_game)
        db.session.commit()
        
        return jsonify({'message': 'Game removed successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to remove game'}), 500


# Image upload endpoint
@vendor_games_bp.route('/games/<int:game_id>/image', methods=['POST'])
def upload_game_image(game_id):
    """
    Upload or update game cover image to Cloudinary
    
    Form data:
        - image: Image file
    """
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    image_file = request.files['image']
    
    if image_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    result = GameService.update_game_image(game_id, image_file)
    
    if result['success']:
        return jsonify({
            'message': 'Image uploaded successfully',
            'image_url': result['image_url'],
            'public_id': result['public_id']
        }), 200
    else:
        return jsonify({'error': result['error']}), 400


# Image delete endpoint
@vendor_games_bp.route('/games/<int:game_id>/image', methods=['DELETE'])
def delete_game_image(game_id):
    """
    Delete game cover image from Cloudinary
    (Reverts to RAWG image if available)
    """
    result = GameService.delete_game_image(game_id)
    
    if result['success']:
        return jsonify({'message': 'Image deleted successfully'}), 200
    else:
        return jsonify({'error': result['error']}), 400


# Get single game details
@vendor_games_bp.route('/games/<int:game_id>', methods=['GET'])
def get_game_details(game_id):
    """
    Get detailed information about a specific game
    """
    from app.models.game import Game
    
    game = Game.query.get(game_id)
    
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    return jsonify(game.to_dict()), 200
