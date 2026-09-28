"""Scheduled end and midnight must not manufacture a completed session."""
import ast
from datetime import datetime, date, time, timedelta, timezone
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'app/routes.py'
tree = ast.parse(SOURCE.read_text())
helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_normalize_lifecycle')
order = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'LIFECYCLE_ORDER' for t in n.targets))
scope = dict(datetime=datetime, date=date, timedelta=timedelta, IST=timezone(timedelta(hours=5, minutes=30)))
exec(compile(ast.Module(body=[order, helper], type_ignores=[]), str(SOURCE), 'exec'), scope)


class ManualSessionEndTests(unittest.TestCase):
    def test_overtime_stays_current(self):
        self.assertEqual(scope['_normalize_lifecycle']('current', date(2000,1,1), time(17), time(18)), 'current')

    def test_overnight_stays_current(self):
        self.assertEqual(scope['_normalize_lifecycle']('current', date(2000,1,1), time(23), time(1)), 'current')

    def test_explicit_terminal_states_remain_terminal(self):
        for status in ['completed', 'cancelled', 'no_show', 'discarded']:
            self.assertEqual(scope['_normalize_lifecycle'](status, date(2099,1,1), time(17), time(18)), status)

    def test_upcoming_is_not_reported_as_played_by_clock(self):
        self.assertEqual(scope['_normalize_lifecycle']('upcoming', date(2000,1,1), time(17), time(18)), 'upcoming')
