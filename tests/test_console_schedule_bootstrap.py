"""Adding hardware must not revive historical schedules or reset held capacity."""
import ast
from datetime import date, datetime, timedelta, time
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import text, tuple_, column


def test_existing_game_bootstrap_keeps_capacity_and_weekday_grid():
    source = Path(__file__).resolve().parents[1] / 'app/services/console_service.py'
    tree = ast.parse(source.read_text())
    original = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ConsoleService')
    names = {'_bootstrap_new_game_slots', '_normalize_day_key', '_row_value', '_parse_time_flexible', '_generate_blocks'}
    selected = [n for n in original.body if isinstance(n, ast.Assign) or isinstance(n, ast.FunctionDef) and n.name in names]
    calls = []
    def execute(sql, params):
        query = str(sql)
        calls.append((query, params))
        if 'FROM vendor_day_slot_config' in query:
            rows = [dict(day='mon', opening_time='00:00', closing_time='00:00', slot_duration=60),
                    dict(day='tue', opening_time='00:00', closing_time='00:00', slot_duration=30)]
        elif 'FROM opening_days' in query:
            rows = [dict(day='mon', is_open=True), dict(day='tue', is_open=False)]
        else: rows = []
        return SimpleNamespace(fetchall=lambda: rows)
    canonical = [SimpleNamespace(id=i+1,start_time=time(i),end_time=time((i+1)%24)) for i in range(24)]
    slot = SimpleNamespace(gaming_type_id=column('gaming_type_id'), start_time=column('start_time'), end_time=column('end_time'),
                           query=SimpleNamespace(filter=lambda *args: SimpleNamespace(all=lambda: canonical)))
    scope = dict(db=SimpleNamespace(session=SimpleNamespace(execute=execute)), Slot=slot,
                 text=text, tuple_=tuple_, date=date, datetime=datetime, timedelta=timedelta)
    cls = ast.ClassDef(name='ConsoleService',bases=[],keywords=[],body=selected,decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),str(source),'exec'),scope)
    service = scope['ConsoleService']
    service._resolve_slot_window_end_date = lambda **kw: date.today()+timedelta(days=20)
    service._bootstrap_new_game_slots(41,120,11,preserve_capacity=True)
    writes = [(sql,params) for sql,params in calls if sql.lstrip().startswith(('INSERT','UPDATE'))]
    assert len(writes) == 1
    assert writes[0][0].lstrip().startswith('INSERT')
    assert writes[0][1]['target_dow'] == 1
    assert writes[0][1]['slot_ids'] == list(range(1,25))
    assert writes[0][1]['available_slot'] == 11

    assert 'existing_template.start_time=template.start_time' in writes[0][0]
    assert 'existing_template.end_time=template.end_time' in writes[0][0]
    assert writes[0][1]['available_game_id'] == 120
