"""The kiosk PC list must carry the same station name the dashboard shows."""
import ast
from pathlib import Path
from types import SimpleNamespace

SRC = Path(__file__).resolve().parents[1] / "app/controllers/vendor_pc_controller.py"


def _station_name():
    tree = ast.parse(SRC.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "station_name")
    scope = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SRC), "exec"), scope)
    return scope["station_name"]


def test_uses_dashboard_console_name():
    assert _station_name()(SimpleNamespace(model_number=" HASH_1 ", console_number=3)) == "HASH_1"


def test_falls_back_to_number_when_name_blank():
    assert _station_name()(SimpleNamespace(model_number="", console_number=3)) == "PC 3"


def test_missing_console():
    assert _station_name()(None) is None


def test_pc_list_and_link_responses_expose_name():
    src = SRC.read_text()
    assert '"name": station_name(c)' in src
    assert '"console_name": station_name(' in src
