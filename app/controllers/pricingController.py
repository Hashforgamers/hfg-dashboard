# controllers/pricingController.py
from flask import Blueprint, request, jsonify, current_app
from app.models.consolePricingOffer import ConsolePricingOffer
from app.models.availableGame import AvailableGame
from app.models.controllerPricingRule import ControllerPricingRule
from app.models.controllerPricingTier import ControllerPricingTier
from app.models.squadPricingRule import SquadPricingRule
from app.models.vendor import Vendor
from app.extension.extensions import db
from datetime import datetime, date, time as dt_time
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload
import pytz
from app.services.websocket_service import socketio
from app.services.console_catalog_service import (
    legacy_console_group,
    normalize_console_slug,
    resolve_console_capabilities,
)

pricing_blueprint = Blueprint('pricing', __name__)

IST = pytz.timezone('Asia/Kolkata')
SUPPORTED_CONTROLLER_POLICIES = {"per_player", "controller_pricing", "optional"}
SQUAD_MAX_PLAYERS_FALLBACK = {"pc": 10}
DEFAULT_SQUAD_POLICY = {
    "pc": {2: 0, 3: 3, 4: 5, 5: 8, 6: 10, 7: 12, 8: 15, 9: 18, 10: 20},
}

def get_ist_now():
    """Returns current datetime in IST"""
    return datetime.now(IST)


def _normalize_console_type(value):
    return normalize_console_slug(value)


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


def _serialize_squad_rules(rules, supported_groups=None):
    supported_groups = supported_groups or SQUAD_MAX_PLAYERS_FALLBACK
    payload = {}
    for group in sorted(supported_groups.keys()):
        payload[group] = {}

    for row in rules:
        group = (row.console_group or "").strip().lower()
        if group not in supported_groups:
            continue
        max_players = int(supported_groups[group])
        if int(row.player_count) < 2 or int(row.player_count) > max_players:
            continue
        payload[group][str(int(row.player_count))] = float(row.discount_percent or 0)
    return payload


def _resolve_squad_group_for_game_name(value, vendor_id=None):
    capabilities = resolve_console_capabilities(vendor_id=vendor_id, raw_console=value)
    if not bool(capabilities.get("supports_multiplayer")):
        return None
    group = legacy_console_group(capabilities.get("slug") or value, capabilities=capabilities)
    if group == "unknown":
        return str(capabilities.get("slug") or "").strip().lower() or None
    return group


def _get_vendor_squad_base_prices(vendor_id: int):
    rows = AvailableGame.query.filter_by(vendor_id=vendor_id).all()
    result = {}
    for game in rows:
        group = _resolve_squad_group_for_game_name(game.game_name, vendor_id=vendor_id)
        if group is None or group in result:
            continue
        result[group] = float(game.single_slot_price or 0)
    return result


def _default_squad_policy(max_players: int):
    baseline = {2: 0, 3: 3, 4: 5, 5: 8, 6: 10, 7: 12, 8: 15, 9: 18, 10: 20}
    max_players = max(2, int(max_players or 2))
    policy = {}
    for players in range(2, max_players + 1):
        if players in baseline:
            policy[str(players)] = float(baseline[players])
        else:
            previous = policy.get(str(players - 1), float(baseline[max(baseline.keys())]))
            policy[str(players)] = float(min(50.0, previous + 2.0))
    return policy


def _get_vendor_controller_capability_map(vendor_id: int):
    result = {}
    for game in AvailableGame.query.filter_by(vendor_id=vendor_id).all():
        slug = normalize_console_slug(game.game_name)
        capabilities = resolve_console_capabilities(vendor_id=vendor_id, raw_console=slug)
        policy = str(capabilities.get("controller_policy") or "").strip().lower()
        if policy not in SUPPORTED_CONTROLLER_POLICIES:
            continue
        key = str(capabilities.get("slug") or slug or game.game_name).strip().lower()
        if not key or key in result:
            continue
        result[key] = {
            "game": game,
            "capabilities": capabilities,
        }
    return result


def _get_vendor_supported_squad_groups(vendor_id: int):
    groups = {}
    for game in AvailableGame.query.filter_by(vendor_id=vendor_id).all():
        capabilities = resolve_console_capabilities(vendor_id=vendor_id, raw_console=game.game_name)
        if not bool(capabilities.get("supports_multiplayer")):
            continue
        group = legacy_console_group(capabilities.get("slug") or game.game_name, capabilities=capabilities)
        if group == "unknown":
            group = str(capabilities.get("slug") or "").strip().lower()
        if not group or group in groups:
            continue
        groups[group] = max(2, int(capabilities.get("default_capacity") or 4))
    return groups or dict(SQUAD_MAX_PLAYERS_FALLBACK)


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

        query = (
            ConsolePricingOffer.query
            .options(joinedload(ConsolePricingOffer.available_game))
            .filter_by(vendor_id=vendor_id)
        )

        available_game_id = request.args.get('available_game_id', type=int)
        if available_game_id:
            query = query.filter_by(available_game_id=available_game_id)

        active_only = request.args.get('active_only', 'false').lower() == 'true'
        if active_only:
            query = query.filter_by(is_active=True)

        offers = query.order_by(ConsolePricingOffer.start_date.desc(), ConsolePricingOffer.id.desc()).all()

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
        current_date = now_ist.date()
        current_time = now_ist.time().replace(tzinfo=None)

        result = {}
        game_ids = [game.id for game in available_games]
        active_offers = (
            ConsolePricingOffer.query
            .filter(
                ConsolePricingOffer.vendor_id == vendor_id,
                ConsolePricingOffer.available_game_id.in_(game_ids),
                ConsolePricingOffer.is_active.is_(True),
                ConsolePricingOffer.start_date <= current_date,
                ConsolePricingOffer.end_date >= current_date,
            )
            .order_by(ConsolePricingOffer.available_game_id.asc(), ConsolePricingOffer.created_at.desc())
            .all()
        )

        offers_by_game = {}
        for offer in active_offers:
            if offer.start_date == offer.end_date:
                is_now_active = offer.start_time <= current_time <= offer.end_time
            elif current_date == offer.start_date:
                is_now_active = current_time >= offer.start_time
            elif current_date == offer.end_date:
                is_now_active = current_time <= offer.end_time
            else:
                is_now_active = True

            if is_now_active and offer.available_game_id not in offers_by_game:
                offers_by_game[offer.available_game_id] = offer

        for game in available_games:
            current_offer = offers_by_game.get(game.id)

            if current_offer:
                pricing_key = _normalize_console_type(game.game_name) or str(game.game_name).strip().lower()
                result[pricing_key] = {
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
                pricing_key = _normalize_console_type(game.game_name) or str(game.game_name).strip().lower()
                result[pricing_key] = {
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
        try:
            socketio.emit("pricing_updated", {"vendor_id": vendor_id}, room=f"vendor_{vendor_id}")
        except Exception:
            current_app.logger.warning("pricing_updated emit failed for vendor %s", vendor_id)

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
        try:
            socketio.emit("pricing_updated", {"vendor_id": vendor_id}, room=f"vendor_{vendor_id}")
        except Exception:
            current_app.logger.warning("pricing_updated emit failed for vendor %s", vendor_id)

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
        try:
            socketio.emit("pricing_updated", {"vendor_id": vendor_id}, room=f"vendor_{vendor_id}")
        except Exception:
            current_app.logger.warning("pricing_updated emit failed for vendor %s", vendor_id)

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

        capability_map = _get_vendor_controller_capability_map(vendor_id)

        pricing = {}
        for console_type in sorted(capability_map.keys()):
            game = capability_map[console_type]["game"]

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

        capability_map = _get_vendor_controller_capability_map(vendor_id)
        game_map = {key: value["game"] for key, value in capability_map.items()}

        updated = []
        errors = []

        for entry in payload_rules:
            console_type = _normalize_console_type(entry.get("console_type"))
            if console_type not in game_map:
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
        try:
            socketio.emit("pricing_updated", {"vendor_id": vendor_id}, room=f"vendor_{vendor_id}")
        except Exception:
            current_app.logger.warning("pricing_updated emit failed for vendor %s", vendor_id)

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

        capability_map = _get_vendor_controller_capability_map(vendor_id)
        if console_type not in capability_map:
            supported_types = sorted(capability_map.keys())
            return jsonify({
                'success': False,
                'message': f'console_type must be one of: {", ".join(supported_types)}'
            }), 400
        if quantity is None or quantity < 0:
            return jsonify({'success': False, 'message': 'quantity must be >= 0'}), 400

        game = capability_map[console_type]["game"]

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


@pricing_blueprint.route('/vendor/<int:vendor_id>/squad-pricing-rules', methods=['GET'])
def get_squad_pricing_rules(vendor_id):
    try:
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'success': False, 'message': 'Vendor not found'}), 404

        supported_groups = _get_vendor_supported_squad_groups(vendor_id)
        rows = (
            SquadPricingRule.query
            .filter_by(vendor_id=vendor_id, is_active=True)
            .order_by(SquadPricingRule.console_group.asc(), SquadPricingRule.player_count.asc())
            .all()
        )
        base_prices = _get_vendor_squad_base_prices(vendor_id)

        pricing = _serialize_squad_rules(rows, supported_groups=supported_groups)
        if not rows:
            pricing = {}
            for group, max_players in supported_groups.items():
                defaults = DEFAULT_SQUAD_POLICY.get(group)
                if defaults:
                    pricing[group] = {str(k): float(v) for k, v in defaults.items() if int(k) <= int(max_players)}
                else:
                    pricing[group] = _default_squad_policy(max_players)

        return jsonify({
            'success': True,
            'pricing': pricing,
            'max_players': supported_groups,
            'base_prices': base_prices,
            'rule_engine_scope': sorted(supported_groups.keys()),
            'note': 'Squad discount rules are capability-driven (supports_multiplayer=true).',
        }), 200
    except Exception as e:
        current_app.logger.error(f"❌ Error fetching squad pricing rules: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pricing_blueprint.route('/vendor/<int:vendor_id>/squad-pricing-rules', methods=['PUT'])
def upsert_squad_pricing_rules(vendor_id):
    try:
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'success': False, 'message': 'Vendor not found'}), 404

        data = request.get_json(silent=True) or {}
        pricing = data.get("pricing")
        if not isinstance(pricing, dict):
            return jsonify({
                'success': False,
                'message': 'Payload must include pricing object'
            }), 400
        base_prices = _get_vendor_squad_base_prices(vendor_id)
        supported_groups = _get_vendor_supported_squad_groups(vendor_id)

        validated_rows = []
        rows_by_group = {group: [] for group in supported_groups.keys()}
        errors = []
        for group, rules in pricing.items():
            normalized_group = str(group or "").strip().lower()
            if normalized_group not in supported_groups:
                continue
            if not isinstance(rules, dict):
                errors.append(f'Rules for "{normalized_group}" must be an object')
                continue

            max_players = int(supported_groups[normalized_group])
            for player_key, discount_value in rules.items():
                try:
                    player_count = int(player_key)
                except (TypeError, ValueError):
                    errors.append(f'Invalid rule for "{normalized_group}" player "{player_key}"')
                    continue

                discount_percent = None
                if isinstance(discount_value, dict):
                    raw_discount = discount_value.get("discount_percent")
                    raw_final_amount = discount_value.get("final_amount")
                    if raw_discount is not None:
                        try:
                            discount_percent = float(raw_discount)
                        except (TypeError, ValueError):
                            errors.append(f'Invalid discount_percent for "{normalized_group}" player {player_count}')
                            continue
                    elif raw_final_amount is not None:
                        try:
                            final_amount = float(raw_final_amount)
                        except (TypeError, ValueError):
                            errors.append(f'Invalid final_amount for "{normalized_group}" player {player_count}')
                            continue
                        base_price = float(base_prices.get(normalized_group, 0) or 0)
                        if base_price <= 0:
                            errors.append(f'Base console price missing for "{normalized_group}"')
                            continue
                        max_total_for_slab = base_price * float(player_count)
                        if final_amount < 0 or final_amount > max_total_for_slab:
                            errors.append(
                                f'final_amount must be between 0 and slab total ({max_total_for_slab}) '
                                f'for "{normalized_group}" player {player_count}'
                            )
                            continue
                        discount_percent = ((max_total_for_slab - final_amount) / max_total_for_slab) * 100.0
                    else:
                        errors.append(f'Provide discount_percent or final_amount for "{normalized_group}" player {player_count}')
                        continue
                else:
                    try:
                        discount_percent = float(discount_value)
                    except (TypeError, ValueError):
                        errors.append(f'Invalid discount value for "{normalized_group}" player {player_count}')
                        continue

                if player_count < 2 or player_count > max_players:
                    errors.append(
                        f'player_count must be between 2 and {max_players} for "{normalized_group}"'
                    )
                    continue
                if discount_percent < 0 or discount_percent > 90:
                    errors.append(
                        f'discount_percent must be between 0 and 90 for "{normalized_group}" player {player_count}'
                    )
                    continue

                row = {
                    "console_group": normalized_group,
                    "player_count": player_count,
                    "discount_percent": round(discount_percent, 2),
                }
                validated_rows.append(row)
                rows_by_group[normalized_group].append(row)

        # Keep rule engine sane: discount should not decrease for higher player count.
        for group, rows_for_group in rows_by_group.items():
            sorted_rows = sorted(rows_for_group, key=lambda item: item["player_count"])
            prev_discount = None
            for row in sorted_rows:
                current_discount = float(row["discount_percent"])
                if prev_discount is not None and current_discount < prev_discount:
                    errors.append(
                        f'discount_percent must be non-decreasing as player_count increases for "{group}"'
                    )
                    break
                prev_discount = current_discount

        if not validated_rows:
            return jsonify({
                'success': False,
                'message': 'At least one squad rule is required',
                'errors': [f'Supported groups: {", ".join(sorted(supported_groups.keys()))}'],
            }), 400

        if errors:
            return jsonify({'success': False, 'message': 'Validation failed', 'errors': errors}), 400

        incoming_keys = {
            (row["console_group"], row["player_count"])
            for row in validated_rows
        }

        existing = SquadPricingRule.query.filter_by(vendor_id=vendor_id).all()
        existing_map = {
            (str(r.console_group).lower(), int(r.player_count)): r
            for r in existing
        }

        for key, row in existing_map.items():
            if key not in incoming_keys:
                row.is_active = False

        for row in validated_rows:
            key = (row["console_group"], row["player_count"])
            db_row = existing_map.get(key)
            if db_row is None:
                db_row = SquadPricingRule(
                    vendor_id=vendor_id,
                    console_group=row["console_group"],
                    player_count=row["player_count"],
                    discount_percent=row["discount_percent"],
                    is_active=True,
                )
                db.session.add(db_row)
            else:
                db_row.discount_percent = row["discount_percent"]
                db_row.is_active = True

        db.session.commit()
        try:
            socketio.emit("pricing_updated", {"vendor_id": vendor_id}, room=f"vendor_{vendor_id}")
        except Exception:
            current_app.logger.warning("pricing_updated emit failed for vendor %s", vendor_id)

        return jsonify({'success': True, 'message': 'Squad pricing rules saved'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error saving squad pricing rules: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
