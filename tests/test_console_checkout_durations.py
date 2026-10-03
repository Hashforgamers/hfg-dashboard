from datetime import datetime, time
import sys
from sqlalchemy import text
from test_cafe_wallet import env


def test_durations_follow_dated_slot_size_and_closing_time(env):
    e = env
    with e.app.app_context():
        pricing = sys.modules['app.services.cafe_session_pricing']
        link = e.db.session.get(e.Link, 1)
        # Replace today's schedule with 60-minute slots from 10:00 to 13:00.
        day = datetime.now().date()
        e.db.session.execute(text('DELETE FROM vendor_1_slot'))
        for i in range(3):
            e.db.session.execute(text('INSERT INTO slots VALUES (:id,100,:start,:end)'),
                                 {'id':900+i,'start':time(10+i),'end':time(11+i)})
            e.db.session.execute(text('INSERT INTO vendor_1_slot(vendor_id,slot_id,date) VALUES (1,:id,:day)'),
                                 {'id':900+i,'day':day})
        assert pricing.console_durations(link, datetime.combine(day,time(10,15))) == [
            {'minutes':60}, {'minutes':120}]
        assert pricing.console_durations(link, datetime.combine(day,time(13))) == []
        # A schedule gap ends the initial checkout window.
        e.db.session.execute(text('DELETE FROM vendor_1_slot WHERE slot_id=901'))
        assert pricing.console_durations(link, datetime.combine(day,time(10,15))) == []
