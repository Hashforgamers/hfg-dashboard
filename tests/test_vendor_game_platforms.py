import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import unittest
import re
from flask import Flask, jsonify, request
from sqlalchemy import create_engine, text, bindparam

ROOT = Path(__file__).resolve().parents[1]

class VendorGamePlatformTests(unittest.TestCase):
    def setUp(self):
        scope = {'re': re}
        catalog = ast.parse((ROOT / 'app/services/console_catalog_service.py').read_text())
        nodes = [n for n in catalog.body if (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == 'LEGACY_CONSOLE_ALIAS') or (isinstance(n, ast.FunctionDef) and n.name in {'_slugify', 'normalize_console_slug'})]
        exec('from typing import *', scope)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'catalog', 'exec'), scope)
        controller = ast.parse((ROOT / 'app/controllers/vendor_games.py').read_text())
        nodes = [n for n in controller.body if isinstance(n, ast.FunctionDef) and n.name in {'_game_catalog_platforms', '_incompatible_consoles', 'add_game_to_consoles'}]
        for node in nodes:
            node.decorator_list = []
        scope.update(text=text, bindparam=bindparam, jsonify=jsonify, request=request)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'vendor-games', 'exec'), scope)
        self.scope = scope

    def test_both_catalog_assignments_are_returned(self):
        engine = create_engine('sqlite://')
        self.addCleanup(engine.dispose)
        conn = engine.connect()
        self.addCleanup(conn.close)
        for sql in [
            'CREATE TABLE console_catalog (id INT, slug TEXT, is_active BOOLEAN)',
            'CREATE TABLE game_console_catalog (game_id INT, console_catalog_id INT, is_active BOOLEAN)',
            "INSERT INTO console_catalog VALUES (1, 'playstation', true), (2, 'xbox', true), (3, 'pc', true)",
            'INSERT INTO game_console_catalog VALUES (6, 1, true), (6, 2, true), (6, 3, false)',
        ]:
            conn.execute(text(sql))
        self.scope['db'] = SimpleNamespace(session=conn)
        self.assertEqual(self.scope['_game_catalog_platforms']([6]), {6: ['playstation', 'xbox']})

    def test_platform_aliases_and_unknown_types(self):
        consoles = [SimpleNamespace(id=i, console_type=t) for i, t in enumerate(['PS5', 'playstation', 'Xbox', 'PC', 'unknown'])]
        self.assertEqual(self.scope['_incompatible_consoles'](consoles, ['playstation', 'xbox']), [3, 4])

    def test_incompatible_submission_is_rejected_before_writes(self):
        game_model, console_model, db = MagicMock(), MagicMock(), MagicMock()
        game_model.query.get.return_value = SimpleNamespace(id=6)
        console_model.query.filter.return_value.all.return_value = [SimpleNamespace(id=10, console_type='pc')]
        self.scope.update(Game=game_model, Console=console_model, db=db, _game_catalog_platforms=lambda ids: {6: ['playstation', 'xbox']})
        with Flask(__name__).test_request_context(json={'game_id':6, 'console_ids':[10]}):
            response, status = self.scope['add_game_to_consoles'](112)
            self.assertEqual(status, 400)
            self.assertIn('incompatible', response.get_json()['error'])
        db.session.add.assert_not_called()
        db.session.commit.assert_not_called()
