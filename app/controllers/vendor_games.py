from flask import Blueprint, jsonify, request
from app.services.game_service import GameService
from app.models.game import Game
from app.models.vendorGame import VendorGame
from app.models.console import Console
from app.models.availableGame import AvailableGame, available_game_console
from app.models.consolePricingOffer import ConsolePricingOffer
from sqlalchemy.orm import joinedload
from datetime import datetime
import pytz
import threading
import time
from app.extension.extensions import db


vendor_games_bp = Blueprint('vendor_games', __name__)
IST = pytz.timezone("Asia/Kolkata")
_VENDOR_GAMES_CACHE = {}
_VENDOR_GAMES_CACHE_TTL_SECONDS = 20
_VENDOR_GAMES_CACHE_LOCK = threading.Lock()


def _vendor_games_cache_get(vendor_id, now_ts):
    with _VENDOR_GAMES_CACHE_LOCK:
        item = _VENDOR_GAMES_CACHE.get(vendor_id)
        if not item:
            return None
        if (now_ts - item["ts"]) >= _VENDOR_GAMES_CACHE_TTL_SECONDS:
            _VENDOR_GAMES_CACHE.pop(vendor_id, None)
            return None
        return item["payload"]


def _vendor_games_cache_set(vendor_id, payload, now_ts):
    with _VENDOR_GAMES_CACHE_LOCK:
        _VENDOR_GAMES_CACHE[vendor_id] = {"ts": now_ts, "payload": payload}


def _vendor_games_cache_invalidate(vendor_id):
    with _VENDOR_GAMES_CACHE_LOCK:
        _VENDOR_GAMES_CACHE.pop(vendor_id, None)


def _offer_is_active_now(offer, now_ist):
    if not offer or not offer.is_active:
        return False

    current_date = now_ist.date()
    current_time = now_ist.time().replace(tzinfo=None)

    if not (offer.start_date <= current_date <= offer.end_date):
        return False

    if offer.start_date == offer.end_date:
        return offer.start_time <= current_time <= offer.end_time
    if current_date == offer.start_date:
        return current_time >= offer.start_time
    if current_date == offer.end_date:
        return current_time <= offer.end_time
    return True


# ==================== AVAILABLE GAMES (PLATFORM TYPES) ====================

@vendor_games_bp.route('/vendor/<int:vendor_id>/available-games', methods=['GET'])
def get_available_games(vendor_id):
    available_games = AvailableGame.query.filter_by(vendor_id=vendor_id).all()
    return jsonify([{
        'id': ag.id,
        'platform_type': ag.game_name.lower(),
        'total_consoles': len(ag.consoles),
        'single_slot_price': float(ag.single_slot_price),
        'consoles': [{
            'id': c.id,
            'console_number': c.console_number,
            'brand': c.brand,
            'model_number': c.model_number
        } for c in ag.consoles]
    } for ag in available_games]), 200


# ==================== CONSOLES FOR SPECIFIC PLATFORM ====================

@vendor_games_bp.route('/vendor/<int:vendor_id>/platforms/<string:platform_type>/consoles', methods=['GET'])
def get_consoles_by_platform(vendor_id, platform_type):
    try:
        platform_type_lower = platform_type.lower()

        available_game = AvailableGame.query.filter(
            AvailableGame.vendor_id == vendor_id,
            db.func.lower(AvailableGame.game_name) == platform_type_lower
        ).first()

        if not available_game:
            consoles = Console.query.filter(
                Console.vendor_id == vendor_id,
                db.func.lower(Console.console_type) == platform_type_lower
            ).all()

            if not consoles:
                return jsonify({'error': f'{platform_type} platform not found for this vendor'}), 404

            return jsonify([{
                'id': c.id,
                'console_number': c.console_number,
                'console_type': c.console_type,
                'brand': c.brand,
                'model_number': c.model_number,
                'serial_number': c.serial_number,
                'description': c.description
            } for c in consoles]), 200

        consoles = available_game.consoles

        if not consoles or len(consoles) == 0:
            consoles = Console.query.filter(
                Console.vendor_id == vendor_id,
                db.func.lower(Console.console_type) == platform_type_lower
            ).all()

        return jsonify([{
            'id': c.id,
            'console_number': c.console_number,
            'console_type': c.console_type,
            'brand': c.brand,
            'model_number': c.model_number,
            'serial_number': c.serial_number,
            'description': c.description
        } for c in consoles]), 200

    except Exception as e:
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500


# ==================== GAME CATALOG ====================

@vendor_games_bp.route('/games', methods=['GET'])
def get_all_games():
    search = request.args.get('search', '').strip()
    if search:
        games = GameService.search_games(search)
    else:
        games = GameService.get_all_games()
    return jsonify([game.to_dict() for game in games])


@vendor_games_bp.route('/games/<int:game_id>', methods=['GET'])
def get_game_details(game_id):
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    return jsonify(game.to_dict()), 200


# ==================== VENDOR GAMES ====================

@vendor_games_bp.route('/vendor/<int:vendor_id>/vendor-games', methods=['GET'])
def list_vendor_games(vendor_id):
    """
    List all games added by vendor with console details.
    price_per_hour is now dynamically computed from AvailableGame + active offers.
    """
    now_ts = time.time()
    cached_payload = _vendor_games_cache_get(vendor_id, now_ts)
    if cached_payload is not None:
        return jsonify(cached_payload), 200

    vendor_games = (
        VendorGame.query
        .options(
            joinedload(VendorGame.game),
            joinedload(VendorGame.console),
        )
        .filter_by(vendor_id=vendor_id, is_available=True)
        .all()
    )

    if not vendor_games:
        payload = []
        _vendor_games_cache_set(vendor_id, payload, now_ts)
        return jsonify(payload), 200

    console_ids = {vg.console_id for vg in vendor_games if vg.console_id}

    mapping_rows = (
        db.session.query(
            AvailableGame.id.label("available_game_id"),
            AvailableGame.single_slot_price.label("single_slot_price"),
            AvailableGame.game_name.label("console_type"),
            available_game_console.c.console_id.label("console_id"),
        )
        .select_from(AvailableGame)
        .join(
            available_game_console,
            available_game_console.c.available_game_id == AvailableGame.id,
        )
        .filter(
            AvailableGame.vendor_id == vendor_id,
            available_game_console.c.console_id.in_(console_ids),
        )
        .all()
    )

    available_game_by_console_id = {}
    for row in mapping_rows:
        available_game_by_console_id[int(row.console_id)] = {
            "available_game_id": int(row.available_game_id),
            "default_price": float(row.single_slot_price or 0),
            "console_type": (row.console_type or "").lower(),
        }

    available_game_ids = [
        v["available_game_id"] for v in available_game_by_console_id.values()
    ]
    offers = []
    if available_game_ids:
        offers = (
            ConsolePricingOffer.query
            .filter(
                ConsolePricingOffer.vendor_id == vendor_id,
                ConsolePricingOffer.available_game_id.in_(available_game_ids),
                ConsolePricingOffer.is_active.is_(True),
            )
            .all()
        )

    now_ist = datetime.now(IST)
    active_offer_by_game_id = {}
    for offer in offers:
        if not _offer_is_active_now(offer, now_ist):
            continue
        existing = active_offer_by_game_id.get(int(offer.available_game_id))
        if existing is None or int(offer.id) > int(existing.id):
            active_offer_by_game_id[int(offer.available_game_id)] = offer

    games_dict = {}
    for vg in vendor_games:
        game_id = vg.game_id
        mapping = available_game_by_console_id.get(int(vg.console_id))
        default_price = float(mapping["default_price"]) if mapping else 0.0
        offer = None
        if mapping:
            offer = active_offer_by_game_id.get(int(mapping["available_game_id"]))
        if offer:
            price_info = {
                "price": float(offer.offered_price),
                "is_offer": True,
                "default_price": default_price,
                "offer_name": offer.offer_name,
                "discount_percentage": offer.get_discount_percentage(),
                "valid_until": f"{offer.end_date} {offer.end_time.strftime('%H:%M')}",
            }
        else:
            price_info = {
                "price": default_price,
                "is_offer": False,
                "default_price": default_price,
                "offer_name": None,
                "discount_percentage": None,
                "valid_until": None,
            }

        if game_id not in games_dict:
            games_dict[game_id] = {
                'game': vg.game.to_dict(),
                'consoles': [],
                'prices': []
            }

        games_dict[game_id]['consoles'].append({
            'id': vg.console.id,
            'console_number': vg.console.console_number,
            'console_type': vg.console.console_type,
            'brand': vg.console.brand,
            'model_number': vg.console.model_number,
            'vendor_game_id': vg.id,
            # ✅ Pricing info from AvailableGame + active offer
            'price_per_hour': price_info['price'],
            'is_offer': price_info.get('is_offer', False),
            'default_price': price_info.get('default_price', 0.0),
            'offer_name': price_info.get('offer_name'),
            'discount_percentage': price_info.get('discount_percentage'),
            'valid_until': price_info.get('valid_until'),
        })
        games_dict[game_id]['prices'].append(price_info['price'])

    result = []
    for game_id, data in games_dict.items():
        result.append({
            'game': data['game'],
            'total_consoles': len(data['consoles']),
            'consoles': data['consoles'],
            'avg_price': sum(data['prices']) / len(data['prices']) if data['prices'] else 0
        })

    _vendor_games_cache_set(vendor_id, result, now_ts)
    return jsonify(result), 200


@vendor_games_bp.route('/vendor/<int:vendor_id>/vendor-games', methods=['POST'])
def add_game_to_consoles(vendor_id):
    """
    Add a game to specific consoles.
    price_per_hour is NO longer accepted — it's derived from AvailableGame automatically.

    Request body:
    {
        "game_id": 3498,
        "console_ids": [1, 2, 5]
    }
    """
    data = request.json

    game_id = data.get('game_id')
    console_ids = data.get('console_ids', [])

    if not game_id:
        return jsonify({'error': 'game_id is required'}), 400

    if not console_ids or len(console_ids) == 0:
        return jsonify({'error': 'At least one console_id is required'}), 400

    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    consoles = Console.query.filter(
        Console.id.in_(console_ids),
        Console.vendor_id == vendor_id
    ).all()

    if len(consoles) != len(console_ids):
        return jsonify({'error': 'One or more console IDs are invalid or do not belong to this vendor'}), 400

    try:
        added_count = 0
        skipped_count = 0

        for console in consoles:
            existing = VendorGame.query.filter_by(
                vendor_id=vendor_id,
                game_id=game_id,
                console_id=console.id
            ).first()

            if existing:
                skipped_count += 1
                continue

            vendor_game = VendorGame(
                vendor_id=vendor_id,
                game_id=game_id,
                console_id=console.id,
                is_available=True
                # ✅ No price_per_hour stored — computed dynamically
            )
            db.session.add(vendor_game)
            added_count += 1

        db.session.commit()
        _vendor_games_cache_invalidate(vendor_id)

        return jsonify({
            'message': f'Game added to {added_count} console(s) successfully',
            'added': added_count,
            'skipped': skipped_count,
            'game': game.to_dict(),
            'consoles': [{
                'id': c.id,
                'console_number': c.console_number,
                'console_type': c.console_type
            } for c in consoles]
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to add game: {str(e)}'}), 500


@vendor_games_bp.route('/vendor/<int:vendor_id>/vendor-games/<int:vendor_game_id>', methods=['PUT'])
def update_vendor_game(vendor_id, vendor_game_id):
    """
    Update a vendor game — only is_available is updatable.
    Price is no longer stored here.
    """
    data = request.json

    try:
        vendor_game = VendorGame.query.filter_by(
            id=vendor_game_id,
            vendor_id=vendor_id
        ).first()

        if not vendor_game:
            return jsonify({'error': 'Vendor game not found'}), 404

        # ✅ Only availability is updatable — price comes from AvailableGame
        if 'is_available' in data:
            vendor_game.is_available = data['is_available']

        # Gracefully inform if price update was attempted
        if 'price_per_hour' in data:
            return jsonify({
                'error': 'price_per_hour cannot be set on vendor games. Update the platform price via AvailableGame or create a pricing offer instead.'
            }), 400

        db.session.commit()
        _vendor_games_cache_invalidate(vendor_id)

        return jsonify({
            'message': 'Game updated successfully',
            'vendor_game': vendor_game.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update game: {str(e)}'}), 500


@vendor_games_bp.route('/vendor/<int:vendor_id>/vendor-games/<int:vendor_game_id>', methods=['DELETE'])
def delete_vendor_game(vendor_id, vendor_game_id):
    try:
        vendor_game = VendorGame.query.filter_by(
            id=vendor_game_id,
            vendor_id=vendor_id
        ).first()

        if not vendor_game:
            return jsonify({'error': 'Vendor game not found'}), 404

        game_name = vendor_game.game.name
        console_number = vendor_game.console.console_number

        db.session.delete(vendor_game)
        db.session.commit()
        _vendor_games_cache_invalidate(vendor_id)

        return jsonify({
            'message': f'{game_name} removed from Console #{console_number} successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to remove game: {str(e)}'}), 500


@vendor_games_bp.route('/vendor/<int:vendor_id>/games/<int:game_id>/bulk-delete', methods=['DELETE'])
def bulk_delete_game(vendor_id, game_id):
    try:
        vendor_games = VendorGame.query.filter_by(
            vendor_id=vendor_id,
            game_id=game_id
        ).all()

        if not vendor_games:
            return jsonify({'error': 'Game not found on any console'}), 404

        count = len(vendor_games)
        game_name = vendor_games[0].game.name

        for vg in vendor_games:
            db.session.delete(vg)

        db.session.commit()
        _vendor_games_cache_invalidate(vendor_id)

        return jsonify({
            'message': f'{game_name} removed from {count} console(s) successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to remove game: {str(e)}'}), 500


# ==================== IMAGE UPLOAD ====================

@vendor_games_bp.route('/games/<int:game_id>/image', methods=['POST'])
def upload_game_image(game_id):
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
    result = GameService.delete_game_image(game_id)

    if result['success']:
        return jsonify({'message': 'Image deleted successfully'}), 200
    else:
        return jsonify({'error': result['error']}), 400
