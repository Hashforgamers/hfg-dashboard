"""Check the dashboard's production eligibility rule without booting services."""
import ast
from datetime import datetime, date, time, timedelta, timezone
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'app/routes.py'
helper = next(n for n in ast.parse(SOURCE.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == '_booking_start_eligibility')


class EarlyStartTests(unittest.TestCase):
    def eligible(self, now, day=date(2026, 9, 28), start=time(18), end=time(19)):
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return now
        scope = dict(datetime=Clock, date=date, timedelta=timedelta, IST=timezone(timedelta(hours=5, minutes=30)))
        exec(compile(ast.Module(body=[helper], type_ignores=[]), str(SOURCE), 'exec'), scope)
        return scope[helper.name](day, start, end)[0]

    def test_five_minute_boundary(self):
        self.assertFalse(self.eligible(datetime(2026, 9, 28, 17, 54, 59)))
        self.assertTrue(self.eligible(datetime(2026, 9, 28, 17, 55)))
        self.assertTrue(self.eligible(datetime(2026, 9, 28, 18)))

    def test_end_time_unchanged(self):
        self.assertTrue(self.eligible(datetime(2026, 9, 28, 19)))
        self.assertFalse(self.eligible(datetime(2026, 9, 28, 19, 0, 1)))

    def test_midnight_and_overnight(self):
        self.assertTrue(self.eligible(datetime(2026, 9, 27, 23, 55), start=time(0), end=time(1)))
        self.assertTrue(self.eligible(datetime(2026, 9, 29, 0, 30), start=time(23), end=time(1)))
        self.assertFalse(self.eligible(datetime(2026, 9, 27, 18)))
        self.assertFalse(self.eligible(datetime(2026, 9, 29, 18)))

    def test_incomplete_schedule(self):
        self.assertFalse(self.eligible(datetime(2026, 9, 28, 18), day=None))


if __name__ == '__main__':
    unittest.main()
