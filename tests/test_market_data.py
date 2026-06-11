import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class MarketDataTest(unittest.TestCase):
    def test_get_orderbook_sends_symbol_and_bearer_token(self):
        from toss.get_orderbook import get_orderbook

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return self._response({"result": {"symbol": "QQQM", "asks": [], "bids": []}})

        result = get_orderbook(
            symbol="QQQM",
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/orderbook?symbol=QQQM")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(result["symbol"], "QQQM")

    def test_get_trades_sends_count_when_present(self):
        from toss.get_trades import get_trades

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            return self._response({"result": [{"price": "10", "volume": "1"}]})

        result = get_trades(
            symbol="AAPL",
            count=5,
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/trades?symbol=AAPL&count=5")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(result[0]["price"], "10")

    def test_get_price_limit_sends_symbol(self):
        from toss.get_price_limit import get_price_limit

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            return self._response({"result": {"upperLimitPrice": "100", "lowerLimitPrice": "50"}})

        result = get_price_limit(
            symbol="005930",
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/price-limits?symbol=005930")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(result["upperLimitPrice"], "100")

    def test_get_candles_sends_interval_count_before_and_adjusted(self):
        from toss.get_candles import get_candles

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            return self._response({"result": {"candles": [{"close": "10"}], "nextBefore": None}})

        result = get_candles(
            symbol="QQQM",
            interval="1m",
            count=10,
            before="2026-03-25T09:00:00+09:00",
            adjusted=False,
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(
            captured["url"],
            "https://example.test/api/v1/candles?symbol=QQQM&interval=1m&count=10&before=2026-03-25T09%3A00%3A00%2B09%3A00&adjusted=false",
        )
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(result["candles"][0]["close"], "10")

    def test_market_data_scripts_can_run_directly(self):
        scripts = (
            "src/toss/get_orderbook.py",
            "src/toss/get_trades.py",
            "src/toss/get_price_limit.py",
            "src/toss/get_candles.py",
        )
        for script in scripts:
            result = subprocess.run(
                [sys.executable, script, "--help"],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

    def _response(self, payload):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        return FakeResponse()


if __name__ == "__main__":
    unittest.main()
