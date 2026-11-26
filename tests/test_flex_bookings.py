"""Flex-start bookings in the kiosk/session engine (real PostgreSQL, see test_cafe_wallet).

Scenario 14: kiosk window and reserved_until follow the flex window; extensions
do not hold a slot twice; ending the session gives every flex hold back.
"""
import sys
import types
from datetime import datetime, timedelta

import pytest
from sqlalchemy import Table, text

from test_cafe_wallet import env  # noqa: F401  (fixture)

FLEX_COLUMNS = ("ALTER TABLE bookings ADD COLUMN start_at timestamptz, ADD COLUMN end_at timestamptz, "
                "ADD COLUMN duration_minutes integer, ADD COLUMN timing_mode varchar(10)")


def engine():
    return sys.modules['app.services.session_extensions']


def flex():
    return sys.modules['app.services.flex_bookings']


def available(e, slot, day):
    return e.db.session.execute(text('SELECT available_slot FROM vendor_1_slot WHERE slot_id=:s AND date=:d'),
                                {'s': slot, 'd': day}).scalar()


def slot_of(moment):
    return 100 + moment.hour * 2 + moment.minute // 30


def live_flex_booking(e, monkeypatch, minutes=50):
    """A checked-in flex booking 'now-5min' for ``minutes`` on console 1, holding every overlapped 30-min slot."""
    from app.services.cafe_slot_reservations import local_window
    from app.services.slot_capacity import reserve_slot
    booking_table = Table('bookings', e.db.metadata, autoload_with=e.db.engine)

    class Booking(e.db.Model):
        __table__ = booking_table
    mod = types.ModuleType('app.models.booking')
    mod.Booking = Booking
    monkeypatch.setitem(sys.modules, mod.__name__, mod)
    for name, kind in [('user_id', 'integer'), ('game_id', 'integer'), ('username', 'varchar')]:
        e.db.session.execute(text(f'ALTER TABLE vendor_1_dashboard ADD COLUMN {name} {kind}'))
    e.db.session.execute(text(FLEX_COLUMNS))
    now = datetime.utcnow()
    local, _ = local_window(now, now)
    start = local.replace(second=0, microsecond=0) - timedelta(minutes=5)
    if start.date() != local.date() or (start + timedelta(minutes=minutes)).date() != start.date():
        pytest.skip('window would cross midnight in this fixture grid')
    end = start + timedelta(minutes=minutes)
    slots = []
    cursor = start.replace(minute=30 * (start.minute // 30))
    while cursor < end:
        slots.append(slot_of(cursor))
        cursor += timedelta(minutes=30)
    base, extra = slots[0], slots[1:]
    e.db.session.execute(text("""INSERT INTO bookings(id,user_id,game_id,slot_id,status,squad_details,start_at,end_at,duration_minutes,timing_mode)
        VALUES(999,1,100,:slot,'checked_in',CAST(:details AS json),:s,:e,:m,'flex')"""),
        {'slot': base, 'details': '{"assigned_console_ids":[1],"slot_units":1}',
         's': start.replace(tzinfo=flex().IST), 'e': end.replace(tzinfo=flex().IST), 'm': minutes})
    e.db.session.execute(text("""INSERT INTO vendor_1_dashboard(console_id,book_status,book_id,date,start_time,end_time,user_id,game_id,username)
        VALUES(1,'current',999,:day,:start,:end,1,100,'Walk-in')"""), {'day': start.date(), 'start': start.time(), 'end': end.time()})
    reserve_slot(e.db.session, 1, base, start.date())
    for slot in extra:
        reserve_slot(e.db.session, 1, slot, start.date())
        e.db.session.add(e.m.CafeSlotReservation(session_id='flex:999', vendor_id=1, slot_id=slot, date=start.date(), units=1))
    e.db.session.commit()
    flex()._columns_ready = False
    return types.SimpleNamespace(start=start, end=end, base=base, extra=extra, day=start.date(), Booking=Booking)


def test_flex_window_lookup_is_empty_for_slot_bookings_and_before_migration(env):
    e = env
    with e.app.app_context():
        flex()._columns_ready = False
        e.db.session.execute(text("INSERT INTO bookings(id,user_id,game_id,slot_id,status) VALUES(5,1,100,120,'confirmed')"))
        e.db.session.commit()
        assert flex().flex_windows([5]) == {}          # columns missing: no query, no error
        e.db.session.execute(text(FLEX_COLUMNS))
        e.db.session.commit()
        flex()._columns_ready = False
        assert flex().flex_windows([5]) == {}          # slot booking (timing_mode NULL)
        e.db.session.execute(text("""UPDATE bookings SET timing_mode='flex', start_at='2026-11-26T04:42:00Z',
            end_at='2026-11-26T06:42:00Z', duration_minutes=120 WHERE id=5"""))
        e.db.session.commit()
        window = flex().flex_windows([5])[5]
        assert window['startAt'] == '2026-11-26T10:12:00+05:30' and window['endAt'] == '2026-11-26T12:12:00+05:30'
        assert window['timingMode'] == 'flex' and window['durationMinutes'] == 120
        assert flex().release_flex_holds(1, 5) == 0


def test_kiosk_follows_flex_window_extension_does_not_double_hold_and_end_releases(env, monkeypatch):
    e = env
    with e.app.app_context():
        w = live_flex_booking(e, monkeypatch)
        before = {s: available(e, s, w.day) for s in [w.base] + w.extra}
        assert all(v == 1 for v in before.values())

        window = sys.modules['app.services.kiosk_runtime'].booking_window(1, 999, 1)
        assert window['timing_mode'] == 'flex' and window['status'] == 'active'
        assert window['end_at'].startswith(w.end.strftime('%Y-%m-%dT%H:%M'))
        c = engine()
        row = c.attach(e.db.session.get(e.Link, 1), {'kind': 'booking', 'id': '999'})
        e.db.session.commit()
        local_end, _ = c.local_window(row.reserved_until, row.reserved_until)
        assert local_end == w.end                      # reserved_until = flex end_at

        q, quote = c.quote(row)
        e.db.session.commit()
        body = {'quote_id': q.id, 'revision': row.revision, 'idempotency_key': 'flex-extension-key', 'credit_consent': False}
        c.continue_session(row, q.id, body)
        e.db.session.commit()
        assert q.status == 'granted'
        runtime_claims = {r.slot_id for r in e.m.CafeSlotReservation.query.filter_by(session_id=row.id, released_at=None)}
        assert not runtime_claims & set(w.extra)       # slots the flex booking already holds are not held twice
        assert all(available(e, s, w.day) == 1 for s in w.extra)

        c.finish(row)
        e.db.session.commit()
        assert e.m.CafeSlotReservation.query.filter_by(session_id='flex:999', released_at=None).count() == 0
        assert e.m.CafeSlotReservation.query.filter_by(session_id=row.id, released_at=None).count() == 0
        assert all(available(e, s, w.day) == 2 for s in [w.base] + w.extra)
        assert e.db.session.get(w.Booking, 999).status == 'completed'


def test_partial_squad_release_keeps_flex_holds_until_last_station(env):
    e = env
    with e.app.app_context():
        from types import SimpleNamespace
        from app.services.slot_capacity import reserve_slot
        c = engine()
        e.db.session.execute(text(FLEX_COLUMNS))
        day = datetime.utcnow().date() + timedelta(days=1)
        e.db.session.execute(text("INSERT INTO vendor_1_dashboard VALUES(1,'current',997,:d,'10:12','11:12')"), {'d': day})
        reserve_slot(e.db.session, 1, 120, day, 2)
        reserve_slot(e.db.session, 1, 121, day, 2)
        reserve_slot(e.db.session, 1, 122, day, 2)
        for slot in (121, 122):
            e.db.session.add(e.m.CafeSlotReservation(session_id='flex:997', vendor_id=1, slot_id=slot, date=day, units=2))
        e.db.session.commit()
        booking = SimpleNamespace(id=997, slot_id=120)
        details = {'slot_units': 2, 'assigned_console_ids': [1, 2]}
        from test_session_extensions import active
        row, _ = active(e)
        c.release_base_booking(row, booking, details, {1, 2}, {1})
        e.db.session.commit()
        assert e.m.CafeSlotReservation.query.filter_by(session_id='flex:997', released_at=None).count() == 2
        c.release_base_booking(SimpleNamespace(id=row.id, vendor_id=1, console_id=2), booking, details, {1, 2}, {1, 2})
        e.db.session.commit()
        assert e.m.CafeSlotReservation.query.filter_by(session_id='flex:997', released_at=None).count() == 0
        assert [available(e, s, day) for s in (120, 121, 122)] == [2, 2, 2]
