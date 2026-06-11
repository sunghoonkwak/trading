import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class OrderInfoTest(unittest.TestCase):
    def test_get_buying_power_sends_currency_and_account_header(self):
        from toss.get_buying_power import get_buying_power

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return self._response({"result": {"currency": "USD", "cashBuyingPower": "3500.5"}})

        buying_power = get_buying_power(
            account_seq=1,
            currency="USD",
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/buying-power?currency=USD")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["headers"]["X-tossinvest-account"], "1")
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(buying_power["cashBuyingPower"], "3500.5")

    def test_get_sellable_quantity_sends_symbol_and_account_header(self):
        from toss.get_sellable_quantity import get_sellable_quantity

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return self._response({"result": {"sellableQuantity": "10"}})

        quantity = get_sellable_quantity(
            account_seq=1,
            symbol="AAPL",
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/sellable-quantity?symbol=AAPL")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["headers"]["X-tossinvest-account"], "1")
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(quantity["sellableQuantity"], "10")

    def test_get_commissions_sends_account_header(self):
        from toss.get_commissions import get_commissions

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return self._response(
                {
                    "result": [
                        {"marketCountry": "KR", "commissionRate": "0.015"},
                        {"marketCountry": "US", "commissionRate": "0.1"},
                    ]
                }
            )

        commissions = get_commissions(
            account_seq=1,
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/commissions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["headers"]["X-tossinvest-account"], "1")
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(commissions[0]["marketCountry"], "KR")

    def test_order_info_scripts_can_run_directly(self):
        scripts = (
            "src/toss/get_buying_power.py",
            "src/toss/get_sellable_quantity.py",
            "src/toss/get_commissions.py",
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
