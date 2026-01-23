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
    games = GameService.get_vendor_games(vendor_id)
    return jsonify([{'vendor_game': vg.to_dict(), 'game': g.to_dict()} for vg, g in games])


@vendor_games_bp.route('/vendor/<int:vendor_id>/games/<int:game_id>', methods=['POST'])
def add_vendor_game(vendor_id, game_id):
    price = request.json.get('price_per_hour', 50.0)
    GameService.add_game_to_vendor(vendor_id, game_id, price)
    return jsonify({'message': 'Game added'}), 201
