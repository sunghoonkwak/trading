import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from infrastructure.kis.ws_parser import normalize_record


def test_websocket_records_replay_with_configured_width():
    fixture_path = ROOT / "tests" / "fixtures" / "kis" / "ws_records.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    columns = fixture["columns"]
    normalized = {
        name: normalize_record(record, columns)
        for name, record in fixture["records"].items()
    }

    assert all(len(record) == len(columns) for record, _note in normalized.values())
    assert normalized["normal"][1] is None
    assert normalized["missing"][1].startswith("padded ")
    assert normalized["extended"][1].startswith("truncated ")
