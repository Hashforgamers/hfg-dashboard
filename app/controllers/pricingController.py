# controllers/pricingController.py
from flask import Blueprint, request, jsonify, current_app
from app.models.consolePricingOffer import ConsolePricingOffer
from app.models.availableGame import AvailableGame
from app.models.vendor import Vendor
from app.extension.extensions import db
from datetime import datetime, date, time as dt_time
from sqlalchemy import and_, or_

pricing_blueprint = Blueprint('pricing', __name__)


# ================================
# 1. GET ALL OFFERS FOR VENDOR
# ================================
@pricing_blueprint.route('/vendor/<int:vendor_id>/pricing-offers', methods=['GET'])
def get_pricing_offers(vendor_id):
    """
    Get all pricing offers for a vendor
    Query params: 
    - ?available_game_id=123 (filter by console type)
    - ?active_only=true (only active offers)
    - ?current_only=true (only currently running offers)
    """
    try:
        # Validate vendor
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'success': False, 'message': 'Vendor not found'}), 404
        
        # Build query
        query = ConsolePricingOffer.query.filter_by(vendor_id=vendor_id)
        
        # Filter by console type (available_game_id)
        available_game_id = request.args.get('available_game_id', type=int)
        if available_game_id:
            query = query.filter_by(available_game_id=available_game_id)
        
        # Filter by active status
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        if active_only:
            query = query.filter_by(is_active=True)
        
        # Get all offers
        offers = query.order_by(ConsolePricingOffer.start_date.desc()).all()
        
        # Filter by currently running (if requested)
        current_only = request.args.get('current_only', 'false').lower() == 'true'
        if current_only:
            offers = [offer for offer in offers if offer.is_currently_active()]
        
        return jsonify({
            'success': True,
            'offers': [offer.to_dict() for offer in offers],
            'count': len(offers)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"❌ Error fetching pricing offers: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ================================
# 2. GET CURRENT ACTIVE PRICING
# ================================
@pricing_blueprint.route('/vendor/<int:vendor_id>/active-pricing', methods=['GET'])
def get_active_pricing(vendor_id):
    """
    Get current active pricing for all console types
    Returns offered_price if there's an active offer, else default_price from AvailableGame
    """
    try:
        # Get all console types (AvailableGames) for this vendor
        available_games = AvailableGame.query.filter_by(vendor_id=vendor_id).all()
        
        if not available_games:
            return jsonify({
                'success': False,
                'message': 'No console types found for this vendor'
            }), 404
        
        result = {}
        
        for game in available_games:
            # Check for active offers
            active_offers = ConsolePricingOffer.query.filter_by(
                vendor_id=vendor_id,
                available_game_id=game.id,
                is_active=True
            ).all()
            
            # Find currently active offer
            current_offer = None
            for offer in active_offers:
                if offer.is_currently_active():
                    current_offer = offer
                    break
            
            # Build response
            if current_offer:
                result[game.game_name.lower()] = {
                    'available_game_id': game.id,
                    'console_type': game.game_name,
                    'price': float(current_offer.offered_price),
                    'is_offer': True,
                    'default_price': float(game.single_slot_price),
                    'offer_name': current_offer.offer_name,
                    'offer_id': current_offer.id,
                    'offer_description': current_offer.offer_description,
                    'discount_percentage': current_offer.get_discount_percentage(),
                    'valid_until': f"{current_offer.end_date} {current_offer.end_time.strftime('%H:%M')}"
                }
            else:
                result[game.game_name.lower()] = {
                    'available_game_id': game.id,
                    'console_type': game.game_name,
                    'price': float(game.single_slot_price),
                    'is_offer': False,
                    'default_price': float(game.single_slot_price)
                }
        
        return jsonify({
            'success': True,
            'pricing': result,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"❌ Error fetching active pricing: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ================================
# 3. CREATE PRICING OFFER
# ================================
@pricing_blueprint.route('/vendor/<int:vendor_id>/pricing-offers', methods=['POST'])
def create_pricing_offer(vendor_id):
    """
    Create a new pricing offer
    Body: {
        "available_game_id": 123,
        "offered_price": 80,
        "start_date": "2026-02-07",
        "start_time": "15:00",
        "end_date": "2026-02-09",
        "end_time": "20:00",
        "offer_name": "Weekend Special",
        "offer_description": "Special weekend discount on PC gaming"
    }
    """
    try:
        data = request.json
        
        # Validate vendor
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'success': False, 'message': 'Vendor not found'}), 404
        
        # Validate available_game
        available_game_id = data.get('available_game_id')
        available_game = AvailableGame.query.filter_by(
            id=available_game_id,
            vendor_id=vendor_id
        ).first()
        
        if not available_game:
            return jsonify({
                'success': False,
                'message': 'Console type not found for this vendor'
            }), 404
        
        # Parse dates and times
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            start_time = datetime.strptime(data['start_time'], '%H:%M').time()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
            end_time = datetime.strptime(data['end_time'], '%H:%M').time()
        except (ValueError, KeyError) as e:
            return jsonify({
                'success': False,
                'message': f'Invalid date/time format: {str(e)}'
            }), 400
        
        # Validate dates
        if end_date < start_date:
            return jsonify({
                'success': False,
                'message': 'End date cannot be before start date'
            }), 400
        
        if start_date == end_date and end_time <= start_time:
            return jsonify({
                'success': False,
                'message': 'End time must be after start time for same-day offers'
            }), 400
        
        # Validate prices
        offered_price = float(data.get('offered_price', 0))
        default_price = float(available_game.single_slot_price)
        
        if offered_price <= 0:
            return jsonify({
                'success': False,
                'message': 'Offered price must be greater than 0'
            }), 400
        
        if offered_price > default_price:
            return jsonify({
                'success': False,
                'message': f'Offered price (₹{offered_price}) cannot be greater than default price (₹{default_price})'
            }), 400
        
        # Check for overlapping offers
        overlapping = ConsolePricingOffer.query.filter(
            ConsolePricingOffer.vendor_id == vendor_id,
            ConsolePricingOffer.available_game_id == available_game_id,
            ConsolePricingOffer.is_active == True,
            or_(
                # New offer starts during existing offer
                and_(
                    ConsolePricingOffer.start_date <= start_date,
                    ConsolePricingOffer.end_date >= start_date
                ),
                # New offer ends during existing offer
                and_(
                    ConsolePricingOffer.start_date <= end_date,
                    ConsolePricingOffer.end_date >= end_date
                ),
                # New offer completely contains existing offer
                and_(
                    ConsolePricingOffer.start_date >= start_date,
                    ConsolePricingOffer.end_date <= end_date
                )
            )
        ).first()
        
        if overlapping:
            return jsonify({
                'success': False,
                'message': f'Overlapping offer exists: {overlapping.offer_name}',
                'overlapping_offer': overlapping.to_dict()
            }), 400
        
        # Create new offer
        new_offer = ConsolePricingOffer(
            vendor_id=vendor_id,
            available_game_id=available_game_id,
            default_price=default_price,
            offered_price=offered_price,
            start_date=start_date,
            start_time=start_time,
            end_date=end_date,
            end_time=end_time,
            offer_name=data.get('offer_name', 'Special Offer'),
            offer_description=data.get('offer_description'),
            is_active=True
        )
        
        db.session.add(new_offer)
        db.session.commit()
        
        current_app.logger.info(f"✅ Created pricing offer for vendor {vendor_id}: {new_offer.offer_name}")
        
        return jsonify({
            'success': True,
            'message': 'Pricing offer created successfully',
            'offer': new_offer.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error creating pricing offer: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


# ================================
# 4. UPDATE PRICING OFFER
# ================================
@pricing_blueprint.route('/vendor/<int:vendor_id>/pricing-offers/<int:offer_id>', methods=['PUT'])
def update_pricing_offer(vendor_id, offer_id):
    """Update an existing pricing offer"""
    try:
        offer = ConsolePricingOffer.query.filter_by(
            id=offer_id,
            vendor_id=vendor_id
        ).first()
        
        if not offer:
            return jsonify({'success': False, 'message': 'Offer not found'}), 404
        
        data = request.json
        
        # Update offered price
        if 'offered_price' in data:
            offered_price = float(data['offered_price'])
            if offered_price > 0 and offered_price <= float(offer.default_price):
                offer.offered_price = offered_price
            else:
                return jsonify({
                    'success': False,
                    'message': 'Invalid offered price'
                }), 400
        
        # Update dates/times
        if 'start_date' in data:
            offer.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        
        if 'start_time' in data:
            offer.start_time = datetime.strptime(data['start_time'], '%H:%M').time()
        
        if 'end_date' in data:
            offer.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        
        if 'end_time' in data:
            offer.end_time = datetime.strptime(data['end_time'], '%H:%M').time()
        
        # Update offer details
        if 'offer_name' in data:
            offer.offer_name = data['offer_name']
        
        if 'offer_description' in data:
            offer.offer_description = data['offer_description']
        
        if 'is_active' in data:
            offer.is_active = bool(data['is_active'])
        
        offer.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        current_app.logger.info(f"✅ Updated pricing offer {offer_id}")
        
        return jsonify({
            'success': True,
            'message': 'Pricing offer updated successfully',
            'offer': offer.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error updating pricing offer: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ================================
# 5. DELETE/DEACTIVATE OFFER
# ================================
@pricing_blueprint.route('/vendor/<int:vendor_id>/pricing-offers/<int:offer_id>', methods=['DELETE'])
def delete_pricing_offer(vendor_id, offer_id):
    """Deactivate a pricing offer (soft delete)"""
    try:
        offer = ConsolePricingOffer.query.filter_by(
            id=offer_id,
            vendor_id=vendor_id
        ).first()
        
        if not offer:
            return jsonify({'success': False, 'message': 'Offer not found'}), 404
        
        # Soft delete - deactivate
        offer.is_active = False
        offer.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        current_app.logger.info(f"✅ Deactivated pricing offer {offer_id}")
        
        return jsonify({
            'success': True,
            'message': 'Pricing offer deactivated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error deleting pricing offer: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# In your controller
@pricing_blueprint.route('/vendor/<int:vendor_id>/available-games', methods=['GET'])
def get_vendor_available_games(vendor_id):
    """Get available games (console types) for vendor"""
    try:
        games = AvailableGame.query.filter_by(vendor_id=vendor_id).all()
        return jsonify({
            'success': True,
            'games': [{
                'id': g.id,
                'game_name': g.game_name,
                'single_slot_price': float(g.single_slot_price)
            } for g in games]
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
