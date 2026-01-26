from flask import Blueprint, jsonify, request
from app.services.game_service import GameService
from flask_jwt_extended import jwt_required, get_jwt_identity

vendor_games_bp = Blueprint('vendor_games', __name__)

@vendor_games_bp.route('/games', methods=['GET'])
def get_all_games():
    """Fetch all available games in the system"""
    games = GameService.get_all_games()
    return jsonify([game.to_dict() for game in games])

@vendor_games_bp.route('/vendor/<int:vendor_id>/games', methods=['GET'])
def list_vendor_games(vendor_id):
    """List all games for a vendor"""
    games = GameService.get_vendor_games(vendor_id)
    return jsonify([{
        'vendor_game': vg.to_dict(), 
        'game': g.to_dict()
    } for vg, g in games])

@vendor_games_bp.route('/vendor/<int:vendor_id>/games/<int:game_id>', methods=['POST'])
def add_vendor_game(vendor_id, game_id):
    """Add a game to vendor with console type specification"""
    data = request.json
    console_type = data.get('console_type')  # ✅ Changed from console_id
    price = data.get('price_per_hour', 50.0)
    max_slots = data.get('max_slots', 1)
    
    # ✅ Updated validation
    if not console_type:
        return jsonify({'error': 'console_type is required'}), 400
    
    try:
        result = GameService.add_game_to_vendor(vendor_id, game_id, console_type, price, max_slots)
        return jsonify({'message': 'Game added successfully', 'vendor_game': result.to_dict()}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to add game'}), 500

# Image upload endpoint
@vendor_games_bp.route('/games/<int:game_id>/image', methods=['POST'])
def upload_game_image(game_id):
    """Upload or update game cover image"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    image_file = request.files['image']
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
    """Delete game cover image"""
    result = GameService.delete_game_image(game_id)
    
    if result['success']:
        return jsonify({'message': 'Image deleted successfully'}), 200
    else:
        return jsonify({'error': result['error']}), 400
