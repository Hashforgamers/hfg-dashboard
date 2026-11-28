"""Floor-map layout for a cafe's gaming stations.

Each console keeps its own grid cell (consoles.map_x / consoles.map_y, both
nullable: a station without a cell is auto-placed by the dashboard). Zone
labels such as "PC Zone" live on one row per cafe in vendor_station_maps.

Everything here takes the SQLAlchemy session explicitly and uses plain SQL
that runs on Postgres and SQLite, so it can be tested without the app.
"""
import json

from sqlalchemy import text

GRID_MAX = 200          # cells per axis; far more than any cafe floor needs
MAX_ZONES = 40
MAX_ZONE_LABEL = 40


class StationMapError(ValueError):
    pass


def _cell(value, field):
    if isinstance(value, bool) or not isinstance(value, int):
        raise StationMapError(f"{field} must be a whole number")
    if not 0 <= value < GRID_MAX:
        raise StationMapError(f"{field} must be between 0 and {GRID_MAX - 1}")
    return value


def normalize_layout(payload):
    """Validate a bulk-save body.

    {"positions": [{"console_id": 7, "x": 0, "y": 2}, {"console_id": 9, "x": null, "y": null}],
     "zones": [{"label": "PC Zone", "x": 0, "y": 0, "w": 4}]}

    x/y null clears a station's cell. "zones" is optional; when present it
    replaces the cafe's zone labels. Two stations may not share a cell.
    """
    if not isinstance(payload, dict):
        raise StationMapError("Body must be a JSON object")
    raw_positions = payload.get("positions", [])
    if not isinstance(raw_positions, list):
        raise StationMapError("positions must be a list")
    positions, seen_ids, taken = [], set(), {}
    for item in raw_positions:
        if not isinstance(item, dict):
            raise StationMapError("Each position must be an object")
        console_id = item.get("console_id")
        if isinstance(console_id, bool) or not isinstance(console_id, int) or console_id <= 0:
            raise StationMapError("console_id must be a positive whole number")
        if console_id in seen_ids:
            raise StationMapError(f"Station {console_id} appears more than once")
        seen_ids.add(console_id)
        x, y = item.get("x"), item.get("y")
        if x is None and y is None:
            positions.append({"console_id": console_id, "x": None, "y": None})
            continue
        if x is None or y is None:
            raise StationMapError("x and y must both be set or both be null")
        cell = (_cell(x, "x"), _cell(y, "y"))
        if cell in taken:
            raise StationMapError(f"Stations {taken[cell]} and {console_id} share the same cell")
        taken[cell] = console_id
        positions.append({"console_id": console_id, "x": cell[0], "y": cell[1]})

    zones = None
    if "zones" in payload:
        raw_zones = payload.get("zones")
        if not isinstance(raw_zones, list):
            raise StationMapError("zones must be a list")
        if len(raw_zones) > MAX_ZONES:
            raise StationMapError(f"At most {MAX_ZONES} zone labels")
        zones = []
        for zone in raw_zones:
            if not isinstance(zone, dict):
                raise StationMapError("Each zone must be an object")
            label = str(zone.get("label") or "").strip()
            if not label:
                raise StationMapError("Zone label is required")
            if len(label) > MAX_ZONE_LABEL:
                raise StationMapError(f"Zone label must be at most {MAX_ZONE_LABEL} characters")
            width = zone.get("w", 1)
            if isinstance(width, bool) or not isinstance(width, int) or not 1 <= width <= 24:
                raise StationMapError("Zone width must be between 1 and 24 cells")
            zones.append({"label": label, "x": _cell(zone.get("x"), "zone x"),
                          "y": _cell(zone.get("y"), "zone y"), "w": width})
    return {"positions": positions, "zones": zones}


def _zones_from_db(value):
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return []
    return value if isinstance(value, list) else []


def load_layout(session, vendor_id):
    rows = session.execute(text(
        "SELECT id, map_x, map_y FROM consoles WHERE vendor_id = :v ORDER BY id"
    ), {"v": int(vendor_id)}).fetchall()
    zone_row = session.execute(text(
        "SELECT zones, updated_at FROM vendor_station_maps WHERE vendor_id = :v"
    ), {"v": int(vendor_id)}).first()
    updated_at = zone_row.updated_at if zone_row else None
    return {
        "vendor_id": int(vendor_id),
        "positions": [{"console_id": r.id, "x": r.map_x, "y": r.map_y} for r in rows if r.map_x is not None],
        "zones": _zones_from_db(zone_row.zones) if zone_row else [],
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at,
    }


def save_layout(session, vendor_id, payload):
    """Apply a validated layout for one cafe. The caller commits."""
    layout = normalize_layout(payload)
    vendor_id = int(vendor_id)
    owned = {r.id: (r.map_x, r.map_y) for r in session.execute(text(
        "SELECT id, map_x, map_y FROM consoles WHERE vendor_id = :v"
    ), {"v": vendor_id}).fetchall()}
    unknown = [p["console_id"] for p in layout["positions"] if p["console_id"] not in owned]
    if unknown:
        raise StationMapError(f"Station(s) {', '.join(map(str, unknown))} do not belong to this cafe")

    # Stations not in the body keep their cell, so check the result as a whole.
    final = dict(owned)
    for p in layout["positions"]:
        final[p["console_id"]] = (p["x"], p["y"])
    occupied = {}
    for console_id, cell in final.items():
        if cell[0] is None:
            continue
        if cell in occupied:
            raise StationMapError(f"Stations {occupied[cell]} and {console_id} share the same cell")
        occupied[cell] = console_id

    for p in layout["positions"]:
        session.execute(text(
            "UPDATE consoles SET map_x = :x, map_y = :y WHERE id = :id AND vendor_id = :v"
        ), {"x": p["x"], "y": p["y"], "id": p["console_id"], "v": vendor_id})
    if layout["zones"] is not None:
        session.execute(text(
            "INSERT INTO vendor_station_maps (vendor_id, zones, updated_at) VALUES (:v, :z, CURRENT_TIMESTAMP) "
            "ON CONFLICT (vendor_id) DO UPDATE SET zones = excluded.zones, updated_at = CURRENT_TIMESTAMP"
        ), {"v": vendor_id, "z": json.dumps(layout["zones"])})
    return load_layout(session, vendor_id)


_columns_ready = False


def map_columns_ready(session):
    """True once consoles.map_x exists, so getConsoles keeps working before the migration runs."""
    global _columns_ready
    if _columns_ready:
        return True
    try:
        from sqlalchemy import inspect
        names = {c["name"] for c in inspect(session.get_bind()).get_columns("consoles")}
        _columns_ready = {"map_x", "map_y"} <= names
    except Exception:
        return False
    return _columns_ready


def schema_ready(session):
    """True when the station-map migration (consoles.map_x/map_y, vendor_station_maps) has run."""
    try:
        from sqlalchemy import inspect
        inspector = inspect(session.get_bind())
        names = {c["name"] for c in inspector.get_columns("consoles")}
        return {"map_x", "map_y"} <= names and inspector.has_table("vendor_station_maps")
    except Exception:
        return False


NOT_MIGRATED_ERROR = "Floor map needs a database update on the server (sql/20261127_station_map_layout.sql)"
