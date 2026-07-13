import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from infrastructure.toss.get_holdings import get_holdings


class FakeHttpResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self._body


def _load_responses():
    fixture_path = ROOT / "tests" / "fixtures" / "toss" / "holdings_responses.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _replay(payload):
    def fake_urlopen(request, timeout):
        return FakeHttpResponse(payload)

    return get_holdings(
        account_seq=1,
        access_token="dummy-access-token",
        base_url="https://example.test",
        urlopen=fake_urlopen,
    )


def test_replays_normal_holdings_response_offline():
    holdings = _replay(_load_responses()["normal"])

    assert holdings["items"] == [
        {
            "symbol": "DUMMY",
            "name": "Dummy Holding",
            "quantity": "3",
        }
    ]


def test_replays_empty_holdings_response_offline():
    holdings = _replay(_load_responses()["empty"])

    assert holdings["items"] == []


def test_replays_null_items_with_current_behavior():
    holdings = _replay(_load_responses()["null_items"])

    assert holdings["items"] is None
