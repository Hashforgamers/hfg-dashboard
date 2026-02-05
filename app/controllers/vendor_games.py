from flask import Blueprint, jsonify, request
from app.services.game_service import GameService
from app.models.game import Game
from app.models.vendorGame import VendorGame
from app.models.console import Console
from app.models.available_game import AvailableGame
from app.extension.extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity

vendor_games_bp = Blueprint('vendor_games', __name__)


# ==================== CONSOLE ENDPOINTS ====================

@vendor_games_bp.route('/vendor/<int:vendor_id>/consoles', methods=['GET'])
def get_vendor_consoles(vendor_id):
    """
    Get all consoles for a vendor
    Query params:
        - console_type: Filter by type (pc, ps5, xbox)
    Example: /vendor/1/consoles?console_type=pc
    """
    console_type = request.args.get('console_type', '').strip().lower()
    
    query = Console.query.filter_by(vendor_id=vendor_id)
    
    if console_type:
        query = query.filter_by(console_type=console_type)
    
    consoles = query.order_by(Console.console_type.asc(), Console.console_number.asc()).all()
    
    return jsonify([{
        'id': c.id,
        'console_number': c.console_number,
        'console_type': c.console_type,
        'brand': c.brand,
        'model_number': c.model_number,
        'serial_number': c.serial_number,
        'description': c.description,
        'release_date': c.release_date.isoformat() if c.release_date else None
    } for c in consoles]), 200


# ==================== GAME ENDPOINTS ====================

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
        games = GameService.search_games(search)
    else:
        games = GameService.get_all_games()
    
    return jsonify([game.to_dict() for game in games])


@vendor_games_bp.route('/games/<int:game_id>', methods=['GET'])
def get_game_details(game_id):
    """
    Get detailed information about a specific game
    """
    game = Game.query.get(game_id)
    
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    return jsonify(game.to_dict()), 200


# ==================== VENDOR GAME MANAGEMENT (Console-Specific) ====================

@vendor_games_bp.route('/vendor/<int:vendor_id>/available-games', methods=['GET'])
def list_vendor_available_games(vendor_id):
    """
    List all available games for a vendor with console details
    Returns games with the specific consoles they're available on
    """
    available_games = AvailableGame.query.filter_by(vendor_id=vendor_id).all()
    
    result = []
    for ag in available_games:
        # Get the actual Game details from games table
        game = Game.query.filter_by(name=ag.game_name).first()
        
        result.append({
            'available_game_id': ag.id,
            'game_name': ag.game_name,
            'total_slots': ag.total_slot,
            'price_per_slot': ag.single_slot_price,
            'game_details': game.to_dict() if game else None,
            'consoles': [{
                'id': console.id,
                'console_number': console.console_number,
                'console_type': console.console_type,
                'brand': console.brand,
                'model_number': console.model_number
            } for console in ag.consoles]
        })
    
    return jsonify(result), 200


@vendor_games_bp.route('/vendor/<int:vendor_id>/available-games', methods=['POST'])
def add_game_to_vendor_consoles(vendor_id):
    """
    Add a game to specific consoles at a vendor
    
    Request body:
    {
        "game_id": 3498,
        "console_ids": [1, 2, 5],  // Array of console IDs
        "price_per_slot": 50.0
    }
    """
    data = request.json
    
    game_id = data.get('game_id')
    console_ids = data.get('console_ids', [])
    price_per_slot = data.get('price_per_slot', 50.0)
    
    # Validation
    if not game_id:
        return jsonify({'error': 'game_id is required'}), 400
    
    if not console_ids or len(console_ids) == 0:
        return jsonify({'error': 'At least one console_id is required'}), 400
    
    if price_per_slot <= 0:
        return jsonify({'error': 'price_per_slot must be greater than 0'}), 400
    
    # Check if game exists
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    # Verify all consoles belong to this vendor
    consoles = Console.query.filter(
        Console.id.in_(console_ids),
        Console.vendor_id == vendor_id
    ).all()
    
    if len(consoles) != len(console_ids):
        return jsonify({'error': 'One or more console IDs are invalid or do not belong to this vendor'}), 400
    
    try:
        # Check if AvailableGame already exists for this game + vendor
        available_game = AvailableGame.query.filter_by(
            vendor_id=vendor_id,
            game_name=game.name
        ).first()
        
        if available_game:
            # Update existing: add new consoles if not already linked
            for console in consoles:
                if console not in available_game.consoles:
                    available_game.consoles.append(console)
            
            # Update total slots and price
            available_game.total_slot = len(available_game.consoles)
            available_game.single_slot_price = price_per_slot
        else:
            # Create new AvailableGame
            available_game = AvailableGame(
                vendor_id=vendor_id,
                game_name=game.name,
                total_slot=len(consoles),
                single_slot_price=price_per_slot
            )
            available_game.consoles = consoles
            db.session.add(available_game)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Game added to consoles successfully',
            'available_game': {
                'id': available_game.id,
                'game_name': available_game.game_name,
                'total_slots': available_game.total_slot,
                'price_per_slot': available_game.single_slot_price,
                'consoles': [{
                    'id': c.id,
                    'console_number': c.console_number,
                    'console_type': c.console_type
                } for c in available_game.consoles]
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to add game: {str(e)}'}), 500


@vendor_games_bp.route('/vendor/<int:vendor_id>/available-games/<int:available_game_id>', methods=['PUT'])
def update_vendor_available_game(vendor_id, available_game_id):
    """
    Update available game configuration (price, consoles)
    
    Request body:
    {
        "console_ids": [1, 3, 4],  // New list of console IDs
        "price_per_slot": 60.0
    }
    """
    data = request.json
    
    try:
        available_game = AvailableGame.query.filter_by(
            id=available_game_id,
            vendor_id=vendor_id
        ).first()
        
        if not available_game:
            return jsonify({'error': 'Available game not found'}), 404
        
        # Update console IDs if provided
        if 'console_ids' in data:
            console_ids = data['console_ids']
            
            if not console_ids or len(console_ids) == 0:
                return jsonify({'error': 'At least one console_id is required'}), 400
            
            # Verify consoles belong to vendor
            consoles = Console.query.filter(
                Console.id.in_(console_ids),
                Console.vendor_id == vendor_id
            ).all()
            
            if len(consoles) != len(console_ids):
                return jsonify({'error': 'One or more console IDs are invalid'}), 400
            
            # Replace consoles
            available_game.consoles = consoles
            available_game.total_slot = len(consoles)
        
        # Update price if provided
        if 'price_per_slot' in data:
            available_game.single_slot_price = data['price_per_slot']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Game updated successfully',
            'available_game': {
                'id': available_game.id,
                'game_name': available_game.game_name,
                'total_slots': available_game.total_slot,
                'price_per_slot': available_game.single_slot_price,
                'consoles': [{
                    'id': c.id,
                    'console_number': c.console_number,
                    'console_type': c.console_type
                } for c in available_game.consoles]
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update game: {str(e)}'}), 500


@vendor_games_bp.route('/vendor/<int:vendor_id>/available-games/<int:available_game_id>', methods=['DELETE'])
def remove_vendor_available_game(vendor_id, available_game_id):
    """
    Remove a game from vendor (deletes all console associations)
    """
    try:
        available_game = AvailableGame.query.filter_by(
            id=available_game_id,
            vendor_id=vendor_id
        ).first()
        
        if not available_game:
            return jsonify({'error': 'Available game not found'}), 404
        
        db.session.delete(available_game)
        db.session.commit()
        
        return jsonify({'message': 'Game removed successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to remove game: {str(e)}'}), 500


@vendor_games_bp.route('/vendor/<int:vendor_id>/available-games/<int:available_game_id>/consoles/<int:console_id>', methods=['DELETE'])
def remove_console_from_game(vendor_id, available_game_id, console_id):
    """
    Remove a specific console from a game
    (Decreases total_slot count)
    """
    try:
        available_game = AvailableGame.query.filter_by(
            id=available_game_id,
            vendor_id=vendor_id
        ).first()
        
        if not available_game:
            return jsonify({'error': 'Available game not found'}), 404
        
        console = Console.query.filter_by(
            id=console_id,
            vendor_id=vendor_id
        ).first()
        
        if not console:
            return jsonify({'error': 'Console not found'}), 404
        
        if console in available_game.consoles:
            available_game.consoles.remove(console)
            available_game.total_slot = len(available_game.consoles)
            
            # If no consoles left, delete the available_game
            if available_game.total_slot == 0:
                db.session.delete(available_game)
            
            db.session.commit()
            return jsonify({'message': 'Console removed from game successfully'}), 200
        else:
            return jsonify({'error': 'Console is not associated with this game'}), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to remove console: {str(e)}'}), 500


# ==================== IMAGE UPLOAD ENDPOINTS ====================

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


# ==================== LEGACY VENDORGAME ENDPOINTS (Keep for backward compatibility) ====================

@vendor_games_bp.route('/vendor/<int:vendor_id>/games', methods=['GET'])
def list_vendor_games(vendor_id):
    """
    LEGACY: List all games for a specific vendor (VendorGame table)
    Returns games with their vendor-specific configuration (console_type, price, etc.)
    """
    games = GameService.get_vendor_games(vendor_id)
    return jsonify([{
        'vendor_game': vg.to_dict(), 
        'game': g.to_dict()
    } for vg, g in games])
