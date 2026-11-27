"""Station floor map: per-console cells, cafe zone labels and the bulk-save endpoint."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[1]


def load_service():
    spec = importlib.util.spec_from_file_location("station_map", ROOT / "app/services/station_map.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


station_map = load_service()


@pytest.fixture
def api():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db = SQLAlchemy(app)
    emitted = []

    tree = ast.parse((ROOT / "app/routes.py").read_text())
    wanted = {"get_station_map", "save_station_map"}
    routes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in routes} == wanted
    for route in routes:
        route.decorator_list = []
        # The routes import the service lazily; point that import at the file under test.
        route.body = [stmt for stmt in route.body if not isinstance(stmt, ast.ImportFrom)]
    scope = dict(
        db=db, request=request, jsonify=jsonify, current_app=app, SQLAlchemyError=SQLAlchemyError,
        _invalidate_vendor_caches=lambda vid: emitted.append(("invalidate", vid)),
        socketio=SimpleNamespace(emit=lambda event, data, room=None: emitted.append((event, data, room))),
        load_layout=station_map.load_layout, save_layout=station_map.save_layout,
        StationMapError=station_map.StationMapError,
    )
    exec(compile(ast.fix_missing_locations(ast.Module(body=routes, type_ignores=[])), "routes.py", "exec"), scope)
    app.add_url_rule("/vendor/<int:vendor_id>/station-map", view_func=scope["get_station_map"], methods=["GET"])
    app.add_url_rule("/vendor/<int:vendor_id>/station-map", endpoint="save", view_func=scope["save_station_map"], methods=["PUT"])

    with app.app_context():
        db.session.execute(text("CREATE TABLE consoles (id INTEGER PRIMARY KEY, vendor_id INTEGER NOT NULL, map_x INTEGER, map_y INTEGER)"))
        db.session.execute(text("CREATE TABLE vendor_station_maps (vendor_id INTEGER PRIMARY KEY, zones TEXT NOT NULL DEFAULT '[]', updated_at TIMESTAMP)"))
        db.session.execute(text("INSERT INTO consoles (id, vendor_id) VALUES (1, 1), (2, 1), (3, 1), (9, 2)"))
        db.session.commit()
        yield SimpleNamespace(client=app.test_client(), db=db, emitted=emitted)


def cells(api, vendor_id=1):
    rows = api.db.session.execute(text("SELECT id, map_x, map_y FROM consoles WHERE vendor_id=:v ORDER BY id"), {"v": vendor_id})
    return {r.id: (r.map_x, r.map_y) for r in rows}


def test_bulk_save_places_stations_and_zone_labels(api):
    body = {"positions": [{"console_id": 1, "x": 0, "y": 0}, {"console_id": 2, "x": 1, "y": 0}],
            "zones": [{"label": " PC Zone ", "x": 0, "y": 0, "w": 4}]}
    res = api.client.put("/vendor/1/station-map", json=body)
    assert res.status_code == 200, res.json
    assert res.json["positions"] == [{"console_id": 1, "x": 0, "y": 0}, {"console_id": 2, "x": 1, "y": 0}]
    assert res.json["zones"] == [{"label": "PC Zone", "x": 0, "y": 0, "w": 4}]
    assert cells(api) == {1: (0, 0), 2: (1, 0), 3: (None, None)}
    assert ("invalidate", 1) in api.emitted
    assert ("station_map_updated", {"vendor_id": 1}, "vendor_1") in api.emitted

    read = api.client.get("/vendor/1/station-map").json
    assert read["positions"] == res.json["positions"] and read["zones"] == res.json["zones"]


def test_unlisted_stations_keep_their_cell_and_null_clears(api):
    api.client.put("/vendor/1/station-map", json={"positions": [{"console_id": 1, "x": 2, "y": 3}, {"console_id": 2, "x": 0, "y": 0}]})
    res = api.client.put("/vendor/1/station-map", json={"positions": [{"console_id": 2, "x": None, "y": None}]})
    assert res.status_code == 200
    assert cells(api) == {1: (2, 3), 2: (None, None), 3: (None, None)}


def test_zones_untouched_when_not_sent(api):
    api.client.put("/vendor/1/station-map", json={"zones": [{"label": "PS Lounge", "x": 0, "y": 5}]})
    api.client.put("/vendor/1/station-map", json={"positions": [{"console_id": 3, "x": 4, "y": 4}]})
    assert api.client.get("/vendor/1/station-map").json["zones"] == [{"label": "PS Lounge", "x": 0, "y": 5, "w": 1}]


def test_station_of_another_cafe_is_rejected_without_change(api):
    res = api.client.put("/vendor/1/station-map", json={"positions": [{"console_id": 1, "x": 0, "y": 0}, {"console_id": 9, "x": 1, "y": 1}]})
    assert res.status_code == 400 and "9" in res.json["error"]
    assert cells(api)[1] == (None, None)
    assert cells(api, 2) == {9: (None, None)}


def test_moving_onto_an_occupied_cell_is_rejected(api):
    api.client.put("/vendor/1/station-map", json={"positions": [{"console_id": 1, "x": 0, "y": 0}]})
    res = api.client.put("/vendor/1/station-map", json={"positions": [{"console_id": 2, "x": 0, "y": 0}]})
    assert res.status_code == 400 and "same cell" in res.json["error"]
    # Swapping two stations in one save is fine.
    api.client.put("/vendor/1/station-map", json={"positions": [{"console_id": 2, "x": 1, "y": 0}]})
    swap = api.client.put("/vendor/1/station-map", json={"positions": [{"console_id": 1, "x": 1, "y": 0}, {"console_id": 2, "x": 0, "y": 0}]})
    assert swap.status_code == 200, swap.json
    assert cells(api)[1] == (1, 0) and cells(api)[2] == (0, 0)


@pytest.mark.parametrize("body", [
    None, [], {"positions": "x"}, {"positions": [{"console_id": 1, "x": 0}]},
    {"positions": [{"console_id": 1, "x": -1, "y": 0}]}, {"positions": [{"console_id": 1, "x": 200, "y": 0}]},
    {"positions": [{"console_id": 1, "x": 1.5, "y": 0}]}, {"positions": [{"console_id": True, "x": 0, "y": 0}]},
    {"positions": [{"console_id": 1, "x": 0, "y": 0}, {"console_id": 1, "x": 1, "y": 0}]},
    {"positions": [{"console_id": 1, "x": 0, "y": 0}, {"console_id": 2, "x": 0, "y": 0}]},
    {"zones": [{"label": "", "x": 0, "y": 0}]}, {"zones": [{"label": "x" * 41, "x": 0, "y": 0}]},
    {"zones": [{"label": "A", "x": 0, "y": 0, "w": 0}]}, {"zones": "PC"},
])
def test_invalid_bodies_are_rejected(api, body):
    res = api.client.put("/vendor/1/station-map", json=body)
    assert res.status_code == 400
    assert cells(api) == {1: (None, None), 2: (None, None), 3: (None, None)}


def test_empty_map_reads_cleanly(api):
    res = api.client.get("/vendor/1/station-map")
    assert res.status_code == 200
    assert res.json["positions"] == [] and res.json["zones"] == []


def test_get_consoles_exposes_map_cell_additively():
    source = (ROOT / "app/routes.py").read_text()
    fn = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "get_consoles")
    body = ast.get_source_segment(source, fn)
    assert '"mapX": row.map_x' in body and '"mapY": row.map_y' in body
    # Works before the migration: the columns fall back to NULL.
    assert "NULL AS map_x, NULL AS map_y" in body


def test_rbac_rules_cover_station_map():
    source = (ROOT / "app/middleware/rbac_guard.py").read_text()
    assert '("GET", r"^/api/vendor/(?P<vendor_id>\\d+)/station-map$", "dashboard.view")' in source
    assert '("PUT", r"^/api/vendor/(?P<vendor_id>\\d+)/station-map$", "gaming.manage")' in source


def test_migration_is_additive_and_idempotent():
    sql = (ROOT / "sql/20261127_station_map_layout.sql").read_text()
    assert "ADD COLUMN IF NOT EXISTS map_x integer" in sql and "ADD COLUMN IF NOT EXISTS map_y integer" in sql
    assert "CREATE TABLE IF NOT EXISTS vendor_station_maps" in sql
    assert "DROP COLUMN" not in sql.upper()
