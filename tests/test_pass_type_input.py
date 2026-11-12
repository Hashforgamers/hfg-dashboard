"""Run pass handlers without initializing unrelated application services."""
import ast
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def handlers(monkeypatch):
    source = Path(__file__).resolve().parents[1] / 'app/routes.py'
    names = {'_normalize_pass_type_id', 'create_vendor_pass', 'update_vendor_pass'}
    nodes = [n for n in ast.parse(source.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    for node in nodes:
        node.decorator_list = []
    existing = SimpleNamespace(id=7, name='Existing', pass_mode='date_based',
                               pass_type_id=3, to_dict=lambda: {})
    model = Mock()
    model.query.filter_by.return_value.first.return_value = existing
    model.return_value = SimpleNamespace(id=8, name='PC Day Pass', to_dict=lambda: {})
    module = ModuleType('app.models.passModels')
    module.CafePass = model
    module.PassType = Mock()
    monkeypatch.setitem(sys.modules, module.__name__, module)
    session = Mock()
    request = Mock()
    scope = dict(request=request, db=SimpleNamespace(session=session),
                 jsonify=lambda value: value, current_app=Mock(), socketio=Mock(),
                 _sync_cafe_specific_pass_payment_method=Mock(),
                 _invalidate_vendor_caches=Mock())
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), scope)
    return SimpleNamespace(scope=scope, model=model, existing=existing,
                           session=session, request=request)


@pytest.mark.parametrize('value,expected', [(None, None), ('', None), ('  ', None),
                                           (3, 3), ('3', 3), (' 3 ', 3)])
@pytest.mark.parametrize('operation', ['create', 'update'])
def test_optional_pass_type(handlers, value, expected, operation):
    h = handlers
    h.request.get_json.return_value = dict(
        name='PC Day Pass', price=700, pass_mode='hour_based', days_valid=1,
        total_hours=10, pc_only=True, pass_type_id=value)
    if operation == 'create':
        _, status = h.scope['create_vendor_pass'](41)
        assert status == 201
        assert h.model.call_args.kwargs['pass_type_id'] == expected
        assert h.model.call_args.kwargs['total_hours'] == 10
    else:
        _, status = h.scope['update_vendor_pass'](41, 7)
        assert status == 200
        assert h.existing.pass_type_id == expected
    h.session.commit.assert_called_once()


@pytest.mark.parametrize('operation', ['create', 'update'])
@pytest.mark.parametrize('value', ['abc', '1.5', 1.5, True, False, [], {}, 0, -1, 2147483648])
def test_invalid_id_returns_400_without_commit(handlers, operation, value):
    h = handlers
    h.request.get_json.return_value = dict(
        name='PC Day Pass', price=700, pass_mode='date_based', days_valid=1,
        pass_type_id=value)
    args = (41,) if operation == 'create' else (41, 7)
    body, status = h.scope[f'{operation}_vendor_pass'](*args)
    assert status == 400
    assert 'pass_type_id' in body['error']
    h.session.commit.assert_not_called()
    h.session.rollback.assert_called_once()


def test_omitted_id_is_optional_on_create_and_preserved_on_update(handlers):
    h = handlers
    h.request.get_json.return_value = dict(
        name='Day Pass', price=700, pass_mode='date_based', days_valid=1)
    assert h.scope['create_vendor_pass'](41)[1] == 201
    assert h.model.call_args.kwargs['pass_type_id'] is None
    assert h.scope['update_vendor_pass'](41, 7)[1] == 200
    assert h.existing.pass_type_id == 3
