import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class GetPricesTest(unittest.TestCase):
    def test_get_prices_sends_symbols_and_bearer_token(self):
        from toss.get_prices import get_prices

        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps(
                    {
                        "result": [
                            {
                                "symbol": "005930",
                                "timestamp": "2026-03-25T09:30:00.123+09:00",
                                "lastPrice": "72000",
                                "currency": "KRW",
                            },
                            {
                                "symbol": "AAPL",
                                "timestamp": "2026-03-25T22:30:00.456+09:00",
                                "lastPrice": "185.70",
                                "currency": "USD",
                            },
                        ]
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return FakeResponse()

        prices = get_prices(
            ["005930", "AAPL"],
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(
            captured["url"],
            "https://example.test/api/v1/prices?symbols=005930%2CAAPL",
        )
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(prices[0]["symbol"], "005930")
        self.assertEqual(prices[0]["lastPrice"], "72000")
        self.assertEqual(prices[1]["currency"], "USD")

    def test_load_access_token_reads_latest_saved_token(self):
        from toss.get_prices import load_access_token

        token_dir = ROOT / "tests" / ".tmp-prices-token"
        self.addCleanup(lambda: self._remove_tree(token_dir))
        token_dir.mkdir()
        (token_dir / "toss_token_20260611_120000.json").write_text(
            json.dumps({"access_token": "old-token"}),
            encoding="utf-8",
        )
        (token_dir / "toss_token_20260611_130000.json").write_text(
            json.dumps({"access_token": "latest-token"}),
            encoding="utf-8",
        )

        self.assertEqual(load_access_token(token_dir), "latest-token")

    def test_script_can_run_directly(self):
        result = subprocess.run(
            [sys.executable, "src/toss/get_prices.py", "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Get Toss Invest current prices.", result.stdout)

    def _remove_tree(self, path):
        if not path.exists():
            return
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


if __name__ == "__main__":
    unittest.main()
