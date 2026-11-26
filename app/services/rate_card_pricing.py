"""Price kiosk extra play (overrun and paid extensions) from the cafe's desk rate card.

Source of truth for the rate-card arithmetic is hfg-booking:
services/desk_pricing.py (quote, legacy_definition, rates_for_game) and
services/extra_play_pricing.py (marginal pricing and card choice). This
service cannot import hfg-booking, so the pure functions below are a copy;
keep them in step with those files. Both services read the same
desk_rate_cards / desk_pricing_settings tables.

Rule: extra play costs the MARGINAL rate-card price of the whole session,
    quote(card, played_before + extra, players) - quote(card, played_before, players)
so a gamer who plays on reaches the owner's cheaper long-session tiers.
Callers cap the result at the old slot-rate price, so this pricing can only
ever lower what a gamer pays for extra time.
"""
import json
import math
import re
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import inspect, text

CENT = Decimal(".01")


# ---- copied from hfg-booking services/desk_pricing.py ------------------------------

def game_rate_key(value):
    if not isinstance(value, str) or len(value) > 120:
        raise ValueError('Choose a game title of up to 120 characters.')
    return re.sub(r'[^a-z0-9]+', '', value.strip().lower())


def rates_for_game(definitions, selected_game):
    """A title override replaces standard rates before duration/player matching."""
    key = game_rate_key(selected_game)
    special = [d for d in definitions if key and game_rate_key(d.get('game_variant', '')) == key]
    return special or [d for d in definitions if not game_rate_key(d.get('game_variant', ''))]


def legacy_definition(profile, rates):
    """Old stored presets, with their historic arithmetic (desk_pricing.legacy_definition)."""
    names = {'pc': 'PC duration rates', 'ps55': 'PS5 · 55 inch', 'ps65': 'PS5 · 65 inch',
             'gta55': 'GTA6 · 55 inch', 'gta65': 'GTA6 · 65 inch', 'racing': 'Racing Sim'}
    if profile not in names:
        raise ValueError("This legacy rate needs a custom pricing definition.")

    def rule(amount, low=1, high=None, players_low=1, players_high=1000, unit=60, each=True):
        return dict(amount=str(Decimal(str(amount)).quantize(CENT)), min_minutes=low, max_minutes=high,
                    min_players=players_low, max_players=players_high, unit_minutes=unit, per_player=each)
    if profile == 'pc':
        rules = [rule(rates[0], 1, 119), rule(rates[1], 120, 180), rule(rates[2], 181)]
    elif profile == 'racing':
        rules = [rule(rates[0], 30, 30, 1, 1, 0, False), rule(rates[1], 60, 60, 1, 1, 0, False)]
    else:
        rules = [rule(rate, players_low=i + 1, players_high=i + 1) for i, rate in enumerate(rates)]
    return dict(name=names[profile], model_name='Imported rates', rules=rules, console_ids=[],
                game_variant='GTA6' if profile.startswith('gta') else '')


# ---- copied from hfg-booking services/extra_play_pricing.py ------------------------

def _rule_for(definition, minutes, players):
    whole = max(1, math.ceil(Decimal(str(minutes))))
    matches = [r for r in definition.get("rules") or []
               if int(r["min_minutes"]) <= whole
               and (r.get("max_minutes") is None or whole <= int(r["max_minutes"]))
               and int(r["min_players"]) <= players <= int(r["max_players"])]
    return matches[0] if len(matches) == 1 else None


def card_quote(definition, minutes, players):
    minutes = Decimal(str(minutes))
    if minutes <= 0:
        return Decimal(0)
    rule = _rule_for(definition, minutes, players)
    if rule is None:
        return None
    total = Decimal(str(rule["amount"])) * (players if rule["per_player"] else 1)
    if int(rule.get("unit_minutes") or 0):
        total = total * minutes / Decimal(int(rule["unit_minutes"]))
    return total.quantize(CENT, rounding=ROUND_HALF_UP)


def marginal_extra(definition, booked_minutes, extra_minutes, players, paid_base=None):
    players = max(1, int(players or 1))
    extra_minutes = Decimal(str(extra_minutes))
    if extra_minutes <= 0:
        return Decimal(0)
    booked_minutes = Decimal(str(max(0, booked_minutes or 0)))
    total = card_quote(definition, booked_minutes + extra_minutes, players)
    if total is not None:
        base = card_quote(definition, booked_minutes, players)
        if base is None and paid_base is not None:
            base = Decimal(str(paid_base))
        if base is not None:
            return max(Decimal(0), total - base)
    alone = card_quote(definition, extra_minutes, players)
    return None if alone is None else max(Decimal(0), alone)


def resolve_definition(card):
    definition = card.get("definition")
    if isinstance(definition, str):
        definition = json.loads(definition)
    rates = card.get("rates") or []
    if isinstance(rates, str):
        rates = json.loads(rates)
    return definition or legacy_definition(card["profile"], rates)


def candidate_cards(cards, *, pricing_mode="slot", stored_profile=None, game_title="", console_id=None):
    usable = []
    for card in cards or []:
        if not card.get("is_active", True) or card.get("archived"):
            continue
        try:
            definition = resolve_definition(card)
            special = bool(game_rate_key(str(definition.get("game_variant") or "")))
        except (ValueError, KeyError, TypeError, IndexError):
            continue
        if pricing_mode != "variants" and not special:
            continue
        usable.append(dict(card, definition=definition))
    if stored_profile:
        own = [c for c in usable if c.get("profile") == stored_profile]
        if own:
            return own
    try:
        allowed = rates_for_game([c["definition"] for c in usable], game_title or "")
    except ValueError:
        allowed = rates_for_game([c["definition"] for c in usable], "")
    usable = [c for c in usable if c["definition"] in allowed]
    if console_id is not None:
        try:
            console = int(console_id)
        except (TypeError, ValueError):
            console = None
        if console is not None:
            mapped = [c for c in usable if console in (c["definition"].get("console_ids") or [])]
            if mapped:
                return mapped
    return [c for c in usable if not c["definition"].get("console_ids")] or (usable if console_id is None else [])


def best_extra_price(cards, booked_minutes, extra_minutes, players, paid_base=None):
    best = (None, None)
    for card in cards:
        price = marginal_extra(card["definition"], booked_minutes, extra_minutes, players, paid_base)
        if price is not None and (best[0] is None or price < best[0]):
            best = (price, card)
    return best


# ---- kiosk runtime ---------------------------------------------------------------

def _tables_ready(db):
    if db.engine.dialect.name == 'postgresql':
        return bool(db.session.execute(text(
            "SELECT to_regclass('desk_rate_cards') IS NOT NULL AND to_regclass('desk_pricing_settings') IS NOT NULL")).scalar())
    names = set(inspect(db.engine).get_table_names())
    return {'desk_rate_cards', 'desk_pricing_settings'} <= names


def _details(db, booking_id):
    value = db.session.execute(text('SELECT squad_details FROM bookings WHERE id=:id'), {'id': booking_id}).scalar()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = None
    return value if isinstance(value, dict) else {}


def session_context(row):
    """(game_id, pricing_mode, cards, players, stored_profile, game_title) for a runtime row, or None."""
    from app.extension.extensions import db
    if not _tables_ready(db):
        return None
    game = db.session.execute(text('''SELECT ag.id FROM available_games ag
        JOIN available_game_console ac ON ac.available_game_id=ag.id
        WHERE ac.console_id=:cid AND ag.vendor_id=:vid ORDER BY ag.id'''),
        {'cid': row.console_id, 'vid': row.vendor_id}).first()
    if not game:
        return None
    mode = db.session.execute(text('SELECT mode FROM desk_pricing_settings WHERE vendor_id=:v AND game_id=:g'),
                              {'v': row.vendor_id, 'g': game.id}).scalar() or 'slot'
    cards = [dict(c) for c in db.session.execute(text('''SELECT profile,revision,definition,rates,is_active,archived
        FROM desk_rate_cards WHERE vendor_id=:v AND game_id=:g AND is_active=true AND archived=false
        ORDER BY profile'''), {'v': row.vendor_id, 'g': game.id}).mappings().all()]
    players, profile, title = 1, None, ''
    booking_ids = list(row.booking_ids or []) if row.source_kind == 'booking' else []
    if booking_ids:
        details = _details(db, int(booking_ids[0]))
        desk = details.get('desk_pricing') if isinstance(details.get('desk_pricing'), dict) else {}
        profile, title = desk.get('profile'), desk.get('selected_game') or ''
        consoles = details.get('assigned_console_ids') or details.get('desk_console_ids') or []
        # A squad spread over several PCs has one runtime per PC: each PC's
        # extra time is one player's. A squad sharing one console plays as a group.
        if not isinstance(consoles, list) or len(consoles) <= 1:
            try:
                players = max(1, int(details.get('player_count') or details.get('playerCount') or 1))
            except (TypeError, ValueError):
                players = 1
    return game.id, mode, cards, players, profile, title


def extra_play_paise(row, start, end):
    """Rate-card price in paise of play from start to end, or None.

    Played-before minutes are start - row.started_at: the booked/reserved
    time plus any extension already granted before this stretch.
    """
    if end <= start or not getattr(row, 'started_at', None):
        return None
    context = session_context(row)
    if not context:
        return None
    _game, mode, cards, players, profile, title = context
    candidates = candidate_cards(cards, pricing_mode=mode, stored_profile=profile,
                                 game_title=title, console_id=row.console_id)
    if not candidates:
        return None
    booked = max(0.0, (start - row.started_at).total_seconds()) / 60.0
    extra = (end - start).total_seconds() / 60.0
    price, _card = best_extra_price(candidates, booked, extra, players)
    if price is None:
        return None
    return int(math.ceil(price * 100))
