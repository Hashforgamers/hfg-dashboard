"""Quote the linked console using Console Pricing, never wallet-policy amounts."""
from datetime import datetime, date, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from sqlalchemy import text
from app.extension.extensions import db
from app.services.pricing_math import session_amount


def session_prices(link, durations, now=None, *, check_capacity=True):
    now = now or datetime.now(ZoneInfo('Asia/Kolkata')).replace(tzinfo=None, second=0, microsecond=0)
    games = db.session.execute(text('''SELECT ag.id,ag.single_slot_price FROM available_games ag
        JOIN available_game_console ac ON ac.available_game_id=ag.id
        WHERE ac.console_id=:cid AND ag.vendor_id=:vid'''), {'cid':link.console_id,'vid':link.vendor_id}).all()
    if len(games) != 1:
        raise ValueError('Link this console to exactly one console pricing record before enabling wallet sessions')
    game = games[0]
    # Slot templates include different weekday schedules and historical timings.
    # Only the vendor's dated schedule identifies the slots for this session.
    last_day = (now + timedelta(minutes=max((d['minutes'] for d in durations), default=0), seconds=45)).date()
    slots = db.session.execute(text(f'''SELECT DISTINCT v.date,v.slot_id,v.available_slot,v.is_available,s.start_time,s.end_time
        FROM VENDOR_{int(link.vendor_id)}_SLOT v JOIN slots s ON s.id=v.slot_id
        WHERE v.vendor_id=:vid AND s.gaming_type_id=:gid
          AND v.date BETWEEN :first_day AND :last_day'''),
        {'vid':link.vendor_id, 'gid':game.id,
         'first_day':now.date()-timedelta(days=1), 'last_day':last_day}).all()
    offers = db.session.execute(text('''SELECT start_date,start_time,end_date,end_time,offered_price,is_active
        FROM console_pricing_offers WHERE vendor_id=:vid AND available_game_id=:gid AND is_active=true'''),
        {'vid':link.vendor_id,'gid':game.id}).all()
    schedule_rows = [dict(row._mapping) for row in slots]
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
            from app.services.cafe_slot_reservations import covered_slots, ensure_console_window
            window_end = now + timedelta(minutes=duration['minutes'], seconds=45)
            covered = covered_slots(schedule_rows, now, window_end)
            if check_capacity and any(not row['is_available'] or row['available_slot'] < 1 for row in covered):
                raise ValueError('Slot is no longer available. Refresh and choose another duration.')
            ensure_console_window(link, now, window_end)
            amount = session_amount(game.single_slot_price, slots, offers, now, duration['minutes'])
            rows.append({'minutes':duration['minutes'], 'amount':amount})
        except ValueError as error:
            rows.append({'minutes':duration['minutes'], 'amount':None, 'unavailable_reason':str(error)})
    return rows


def affordable_duration(link, available_balance, durations, now=None):
    """Longest whole-minute session the available wallet covers, within cafe limits."""
    if available_balance <= 0 or not durations:
        return None
    now=now or datetime.now(ZoneInfo('Asia/Kolkata')).replace(tzinfo=None,second=0,microsecond=0)
    low, high, best = 5, max(d['minutes'] for d in durations), None
    # Nonnegative slot prices make the cumulative price monotonic; coverage,
    # capacity and physical console conflicts also cannot recover at a later end.
    while low <= high:
        minutes = (low+high)//2
        quote = session_prices(link,[{'minutes':minutes}],now=now)[0]
        if quote['amount'] is not None and quote['amount'] <= available_balance:
            best=quote;low=minutes+1
        else:
            high=minutes-1
    return best
