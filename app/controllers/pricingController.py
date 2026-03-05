# controllers/pricingController.py
from flask import Blueprint, request, jsonify, current_app
from app.models.consolePricingOffer import ConsolePricingOffer
from app.models.availableGame import AvailableGame
from app.models.controllerPricingRule import ControllerPricingRule
from app.models.controllerPricingTier import ControllerPricingTier
from app.models.vendor import Vendor
from app.extension.extensions import db
from datetime import datetime, date, time as dt_time
from sqlalchemy import and_, or_
import pytz

pricing_blueprint = Blueprint('pricing', __name__)

IST = pytz.timezone('Asia/Kolkata')
SUPPORTED_CONTROLLER_TYPES = {"ps5", "xbox"}

def get_ist_now():
    """Returns current datetime in IST"""
    return datetime.now(IST)


def _normalize_console_type(value):
    text = str(value or "").strip().lower()
    if "ps" in text:
        return "ps5"
    if "xbox" in text:
        return "xbox"
    return text


def _calculate_controller_total(base_price, tiers, quantity):
    if quantity <= 0:
        return 0.0

    dp = [float("inf")] * (quantity + 1)
    dp[0] = 0.0

    for q in range(1, quantity + 1):
        dp[q] = min(dp[q], dp[q - 1] + base_price)
        for tier in tiers:
            tier_qty = int(tier["quantity"])
            tier_total = float(tier["total_price"])
            if tier_qty <= q:
                dp[q] = min(dp[q], dp[q - tier_qty] + tier_total)

    return float(dp[quantity] if dp[quantity] != float("inf") else quantity * base_price)


def _serialize_controller_rule(rule, console_type, available_game_id):
    active_tiers = [tier.to_dict() for tier in rule.tiers if tier.is_active]
    active_tiers.sort(key=lambda t: t["quantity"])
    return {
        "console_type": console_type,
        "available_game_id": available_game_id,
        "base_price": float(rule.base_price),
        "tiers": active_tiers,
        "is_active": rule.is_active,
    }


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
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'success': False, 'message': 'Vendor not found'}), 404

        query = ConsolePricingOffer.query.filter_by(vendor_id=vendor_id)

        available_game_id = request.args.get('available_game_id', type=int)
        if available_game_id:
            query = query.filter_by(available_game_id=available_game_id)

        active_only = request.args.get('active_only', 'false').lower() == 'true'
        if active_only:
            query = query.filter_by(is_active=True)

        offers = query.order_by(ConsolePricingOffer.start_date.desc()).all()

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
    Get current active pricing for all console types.
    Returns offered_price if there's an active offer, else default single_slot_price.
    Uses IST for all time comparisons.
    """
    try:
        available_games = AvailableGame.query.filter_by(vendor_id=vendor_id).all()

        if not available_games:
            return jsonify({
                'success': False,
                'message': 'No console types found for this vendor'
            }), 404

        now_ist = get_ist_now()
        current_app.logger.info(f"🕐 Current IST time: {now_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        result = {}

        for game in available_games:
            active_offers = ConsolePricingOffer.query.filter_by(
                vendor_id=vendor_id,
                available_game_id=game.id,
                is_active=True
            ).all()

            current_offer = next(
                (offer for offer in active_offers if offer.is_currently_active()),
                None
            )

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
            'timestamp': now_ist.isoformat()
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
    Create a new pricing offer.
    Body: {
        "available_game_id": 123,
        "offered_price": 80,
        "start_date": "2026-02-18",
        "start_time": "15:00",
        "end_date": "2026-02-20",
        "end_time": "20:00",
        "offer_name": "Weekend Special",
        "offer_description": "Special weekend discount"
    }
    """
    try:
        data = request.json

        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'success': False, 'message': 'Vendor not found'}), 404

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
                'message': f'Offered price (₹{offered_price}) cannot exceed default price (₹{default_price})'
            }), 400

        # Check for overlapping active offers
        overlapping = ConsolePricingOffer.query.filter(
            ConsolePricingOffer.vendor_id == vendor_id,
            ConsolePricingOffer.available_game_id == available_game_id,
            ConsolePricingOffer.is_active == True,
            or_(
                and_(
                    ConsolePricingOffer.start_date <= start_date,
                    ConsolePricingOffer.end_date >= start_date
                ),
                and_(
                    ConsolePricingOffer.start_date <= end_date,
                    ConsolePricingOffer.end_date >= end_date
                ),
                and_(
                    ConsolePricingOffer.start_date >= start_date,
                    ConsolePricingOffer.end_date <= end_date
                )
            )
        ).first()

        if overlapping:
            return jsonify({
                'success': False,
                'message': f'Overlapping offer exists: "{overlapping.offer_name}"',
                'overlapping_offer': overlapping.to_dict()
            }), 400

        now_ist = get_ist_now().replace(tzinfo=None)

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
            is_active=True,
            created_at=now_ist,
            updated_at=now_ist
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

        if 'offered_price' in data:
            offered_price = float(data['offered_price'])
            if offered_price <= 0 or offered_price > float(offer.default_price):
                return jsonify({
                    'success': False,
                    'message': f'Offered price must be > 0 and ≤ ₹{offer.default_price}'
                }), 400
            offer.offered_price = offered_price

        if 'start_date' in data:
            offer.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()

        if 'start_time' in data:
            offer.start_time = datetime.strptime(data['start_time'], '%H:%M').time()

        if 'end_date' in data:
            offer.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()

        if 'end_time' in data:
            offer.end_time = datetime.strptime(data['end_time'], '%H:%M').time()

        if 'offer_name' in data:
            offer.offer_name = data['offer_name']

        if 'offer_description' in data:
            offer.offer_description = data['offer_description']

        if 'is_active' in data:
            offer.is_active = bool(data['is_active'])

        # ✅ Use IST for updated_at
        offer.updated_at = get_ist_now().replace(tzinfo=None)

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
    """Soft delete — deactivates the pricing offer"""
    try:
        offer = ConsolePricingOffer.query.filter_by(
            id=offer_id,
            vendor_id=vendor_id
        ).first()

        if not offer:
            return jsonify({'success': False, 'message': 'Offer not found'}), 404

        offer.is_active = False
        # ✅ Use IST for updated_at
        offer.updated_at = get_ist_now().replace(tzinfo=None)

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


# ================================
# 6. GET AVAILABLE GAMES FOR VENDOR
# ================================
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


@pricing_blueprint.route('/vendor/<int:vendor_id>/controller-pricing', methods=['GET'])
def get_controller_pricing(vendor_id):
    try:
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'success': False, 'message': 'Vendor not found'}), 404

        available_games = AvailableGame.query.filter_by(vendor_id=vendor_id).all()
        game_map = {_normalize_console_type(game.game_name): game for game in available_games}

        pricing = {}
        for console_type in sorted(SUPPORTED_CONTROLLER_TYPES):
            game = game_map.get(console_type)
            if not game:
                pricing[console_type] = {
                    "console_type": console_type,
                    "available_game_id": None,
                    "base_price": 0.0,
                    "tiers": [],
                    "is_active": False,
                    "configured": False,
                }
                continue

            rule = ControllerPricingRule.query.filter_by(
                vendor_id=vendor_id,
                available_game_id=game.id,
                is_active=True
            ).first()

            if not rule:
                pricing[console_type] = {
                    "console_type": console_type,
                    "available_game_id": game.id,
                    "base_price": 0.0,
                    "tiers": [],
                    "is_active": False,
                    "configured": False,
                }
                continue

            serialized = _serialize_controller_rule(rule, console_type, game.id)
            serialized["configured"] = True
            pricing[console_type] = serialized

        return jsonify({'success': True, 'pricing': pricing}), 200
    except Exception as e:
        current_app.logger.error(f"❌ Error fetching controller pricing: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pricing_blueprint.route('/vendor/<int:vendor_id>/controller-pricing', methods=['PUT'])
def upsert_controller_pricing(vendor_id):
    try:
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'success': False, 'message': 'Vendor not found'}), 404

        data = request.get_json(silent=True) or {}
        payload_rules = []

        if isinstance(data.get("pricing"), dict):
            for console_type, rule_data in data["pricing"].items():
                payload_rules.append({
                    "console_type": console_type,
                    "base_price": rule_data.get("base_price", 0),
                    "tiers": rule_data.get("tiers", []),
                })
        elif isinstance(data.get("rules"), list):
            payload_rules = data["rules"]
        else:
            return jsonify({
                'success': False,
                'message': 'Payload must include "pricing" object or "rules" array'
            }), 400

        if not payload_rules:
            return jsonify({'success': False, 'message': 'No controller pricing rules provided'}), 400

        available_games = AvailableGame.query.filter_by(vendor_id=vendor_id).all()
        game_map = {_normalize_console_type(game.game_name): game for game in available_games}

        updated = []
        errors = []

        for entry in payload_rules:
            console_type = _normalize_console_type(entry.get("console_type"))
            if console_type not in SUPPORTED_CONTROLLER_TYPES:
                # Ignore unsupported keys like pc/vr so mixed payloads don't fail.
                continue

            game = game_map.get(console_type)
            if not game:
                errors.append(f'No available game configured for console_type "{console_type}"')
                continue

            try:
                base_price = float(entry.get("base_price", 0))
            except (TypeError, ValueError):
                errors.append(f'Invalid base_price for "{console_type}"')
                continue

            if base_price < 0:
                errors.append(f'base_price cannot be negative for "{console_type}"')
                continue

            incoming_tiers = entry.get("tiers") or []
            normalized_tiers = []
            tier_quantities = set()
            tier_error = None

            for tier in incoming_tiers:
                try:
                    quantity = int(tier.get("quantity"))
                    total_price = float(tier.get("total_price"))
                except (TypeError, ValueError):
                    tier_error = f'Invalid tier values for "{console_type}"'
                    break

                if quantity < 2:
                    tier_error = f'Tier quantity must be >= 2 for "{console_type}"'
                    break
                if total_price < 0:
                    tier_error = f'Tier total_price cannot be negative for "{console_type}"'
                    break
                if quantity in tier_quantities:
                    tier_error = f'Duplicate tier quantity {quantity} for "{console_type}"'
                    break

                tier_quantities.add(quantity)
                normalized_tiers.append({"quantity": quantity, "total_price": total_price})

            if tier_error:
                errors.append(tier_error)
                continue

            rule = ControllerPricingRule.query.filter_by(
                vendor_id=vendor_id,
                available_game_id=game.id
            ).first()

            if not rule:
                rule = ControllerPricingRule(
                    vendor_id=vendor_id,
                    available_game_id=game.id,
                    base_price=base_price,
                    is_active=True
                )
                db.session.add(rule)
                db.session.flush()
            else:
                rule.base_price = base_price
                rule.is_active = True

            ControllerPricingTier.query.filter_by(rule_id=rule.id).delete()
            db.session.flush()

            for tier in normalized_tiers:
                db.session.add(
                    ControllerPricingTier(
                        rule_id=rule.id,
                        quantity=tier["quantity"],
                        total_price=tier["total_price"],
                        is_active=True
                    )
                )

            db.session.flush()
            db.session.refresh(rule)
            updated.append(_serialize_controller_rule(rule, console_type, game.id))

        if errors:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Validation failed', 'errors': errors}), 400

        db.session.commit()

        return jsonify({'success': True, 'updated_rules': updated}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error saving controller pricing: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pricing_blueprint.route('/vendor/<int:vendor_id>/controller-pricing/calculate', methods=['GET'])
def calculate_controller_pricing(vendor_id):
    try:
        console_type = _normalize_console_type(request.args.get("console_type"))
        quantity = request.args.get("quantity", type=int)

        if console_type not in SUPPORTED_CONTROLLER_TYPES:
            return jsonify({'success': False, 'message': 'console_type must be ps5 or xbox'}), 400
        if quantity is None or quantity < 0:
            return jsonify({'success': False, 'message': 'quantity must be >= 0'}), 400

        game = next(
            (
                g for g in AvailableGame.query.filter_by(vendor_id=vendor_id).all()
                if _normalize_console_type(g.game_name) == console_type
            ),
            None
        )

        if not game:
            return jsonify({'success': False, 'message': f'Console type "{console_type}" not configured'}), 404

        rule = ControllerPricingRule.query.filter_by(
            vendor_id=vendor_id,
            available_game_id=game.id,
            is_active=True
        ).first()

        if not rule:
            return jsonify({
                'success': True,
                'console_type': console_type,
                'quantity': quantity,
                'total_price': 0.0,
                'base_price': 0.0,
                'applied': 'no_rule',
            }), 200

        tiers = [tier.to_dict() for tier in rule.tiers if tier.is_active]
        total_price = _calculate_controller_total(float(rule.base_price), tiers, quantity)

        return jsonify({
            'success': True,
            'console_type': console_type,
            'quantity': quantity,
            'total_price': total_price,
            'base_price': float(rule.base_price),
            'tiers': tiers,
            'applied': 'rule',
        }), 200
    except Exception as e:
        current_app.logger.error(f"❌ Error calculating controller pricing: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
