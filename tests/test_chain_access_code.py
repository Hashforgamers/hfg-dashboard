"""Back-to-back bookings started together share one access code (console guard)."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]


def load(rows, new_code_id=55):
    session = MagicMock()
    calls = []

    def execute(sql, params=None):
        sql = str(sql)
        calls.append((sql, params))
        result = MagicMock()
        result.fetchall.return_value = rows
        result.scalar.return_value = new_code_id
        return result
    session.execute.side_effect = execute
    tree = ast.parse((ROOT / 'app/routes.py').read_text())
    nodes = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name == '_share_chain_access_code')
             or (isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == '_ACCESS_CODE_ALPHABET')]
    scope = dict(db=SimpleNamespace(session=session), text=lambda s: s)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'routes', 'exec'), scope)
    return scope['_share_chain_access_code'], calls


def row(i, user=7, game=120, code=None):
    return SimpleNamespace(id=i, user_id=user, game_id=game, access_code_id=code)


def test_reuses_existing_code_for_uncoded_slot():
    fn, calls = load([row(1280, code=9), row(1281)])
    assert fn([1280, 1281]) == 9
    assert calls[-1][1] == {'cid': 9, 'ids': [1281]}
    assert not any('INSERT' in sql for sql, _ in calls)


def test_creates_code_when_none_exists():
    fn, calls = load([row(1280), row(1281)])
    assert fn([1281, 1280]) == 55
    assert any('INSERT INTO access_booking_codes' in sql for sql, _ in calls)
    assert calls[-1][1] == {'cid': 55, 'ids': [1280, 1281]}


def test_leaves_other_gamers_and_single_bookings_alone():
    fn, calls = load([row(1280), row(1300, user=8)])
    assert fn([1280, 1300]) is None
    assert not any('SET access_code_id' in sql for sql, _ in calls)
    fn, calls = load([row(1280)])
    assert fn([1280]) is None and calls == []
