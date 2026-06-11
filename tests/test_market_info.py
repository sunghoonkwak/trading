import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class MarketInfoTest(unittest.TestCase):
    def test_get_exchange_rate_sends_currency_query_and_bearer_token(self):
        from toss.get_exchange_rate import get_exchange_rate

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return self._response({"result": {"baseCurrency": "USD", "quoteCurrency": "KRW", "rate": "1380.5"}})

        result = get_exchange_rate(
            base_currency="USD",
            quote_currency="KRW",
            date_time="2026-03-25T09:30:00+09:00",
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(
            captured["url"],
            "https://example.test/api/v1/exchange-rate?baseCurrency=USD&quoteCurrency=KRW&dateTime=2026-03-25T09%3A30%3A00%2B09%3A00",
        )
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(result["rate"], "1380.5")

    def test_get_kr_market_calendar_sends_optional_date(self):
        from toss.get_kr_market_calendar import get_kr_market_calendar

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            return self._response({"result": {"today": {"date": "2026-03-25"}}})

        result = get_kr_market_calendar(
            access_token="access-token",
            date="2026-03-25",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/market-calendar/KR?date=2026-03-25")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(result["today"]["date"], "2026-03-25")

    def test_get_us_market_calendar_sends_optional_date(self):
        from toss.get_us_market_calendar import get_us_market_calendar

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            return self._response({"result": {"today": {"date": "2026-03-25"}}})

        result = get_us_market_calendar(
            access_token="access-token",
            date="2026-03-25",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/market-calendar/US?date=2026-03-25")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(result["today"]["date"], "2026-03-25")

    def test_market_info_scripts_can_run_directly(self):
        scripts = (
            "src/toss/get_exchange_rate.py",
            "src/toss/get_kr_market_calendar.py",
            "src/toss/get_us_market_calendar.py",
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
