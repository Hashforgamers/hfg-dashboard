"""Quote the linked console using Console Pricing, never wallet-policy amounts."""
from datetime import datetime, date, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from sqlalchemy import text
from app.extension.extensions import db
from app.services.pricing_math import session_amount


def session_prices(link, durations, now=None):
    now = now or datetime.now(ZoneInfo('Asia/Kolkata')).replace(tzinfo=None, second=0, microsecond=0)
    games = db.session.execute(text('''SELECT ag.id,ag.single_slot_price FROM available_games ag
        JOIN available_game_console ac ON ac.available_game_id=ag.id
        WHERE ac.console_id=:cid AND ag.vendor_id=:vid'''), {'cid':link.console_id,'vid':link.vendor_id}).all()
    if len(games) != 1:
        raise ValueError('Link this console to exactly one console pricing record before enabling wallet sessions')
    game = games[0]
    # Slot templates include different weekday schedules and historical timings.
    # Only the vendor's dated schedule identifies the slots for this session.
    last_day = (now + timedelta(minutes=max((d['minutes'] for d in durations), default=0))).date()
    slots = db.session.execute(text(f'''SELECT DISTINCT v.date,s.start_time,s.end_time
        FROM VENDOR_{int(link.vendor_id)}_SLOT v JOIN slots s ON s.id=v.slot_id
        WHERE v.vendor_id=:vid AND s.gaming_type_id=:gid
          AND v.date BETWEEN :first_day AND :last_day'''),
        {'vid':link.vendor_id, 'gid':game.id,
         'first_day':now.date()-timedelta(days=1), 'last_day':last_day}).all()
    offers = db.session.execute(text('''SELECT start_date,start_time,end_date,end_time,offered_price,is_active
        FROM console_pricing_offers WHERE vendor_id=:vid AND available_game_id=:gid AND is_active=true'''),
        {'vid':link.vendor_id,'gid':game.id}).all()
    slots = [SimpleNamespace(date=date.fromisoformat(row.date) if isinstance(row.date,str) else row.date,
        start_time=time.fromisoformat(row.start_time) if isinstance(row.start_time,str) else row.start_time,
        end_time=time.fromisoformat(row.end_time) if isinstance(row.end_time,str) else row.end_time) for row in slots]
    typed_offers = []
    for row in offers:
        values = dict(row._mapping)
        for name in ('start_date','end_date'):
            if isinstance(values[name],str): values[name] = date.fromisoformat(values[name])
        for name in ('start_time','end_time'):
            if isinstance(values[name],str): values[name] = time.fromisoformat(values[name])
        typed_offers.append(SimpleNamespace(**values))
    offers = typed_offers
    # PostgreSQL returns date/time values directly.
    rows = []
    for duration in durations:
        try:
            amount = session_amount(game.single_slot_price, slots, offers, now, duration['minutes'])
            rows.append({'minutes':duration['minutes'], 'amount':amount})
        except ValueError as error:
            rows.append({'minutes':duration['minutes'], 'amount':None, 'unavailable_reason':str(error)})
    return rows
