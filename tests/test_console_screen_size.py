"""Screen-size input validation used by console create and update."""
import ast
from pathlib import Path
import pytest


def validator():
    source = Path(__file__).resolve().parents[1] / 'app/services/console_service.py'
    tree = ast.parse(source.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ConsoleService')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'normalize_screen_size')
    method.decorator_list = []
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), str(source), 'exec'), scope)
    return scope['normalize_screen_size']


@pytest.mark.parametrize('value,expected', [(None,None),('',None),('  ',None),(55,55),('65',65),(1,1),(1000,1000),(43,43),(85,85)])
def test_screen_size_accepts_real_sizes_and_unset(value, expected):
    assert validator()(value) == expected


@pytest.mark.parametrize('value', [True, False, 0, 1001, -1, 55.5, '55 inches', 'NaN'])
def test_screen_size_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        validator()(value)
