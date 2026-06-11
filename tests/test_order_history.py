import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class OrderHistoryTest(unittest.TestCase):
    def test_get_orders_sends_status_filters_and_account_header(self):
        from toss.get_orders import get_orders

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return self._response(
                {
                    "result": {
                        "orders": [{"orderId": "order-1", "symbol": "AAPL"}],
                        "nextCursor": None,
                        "hasNext": False,
                    }
                }
            )

        orders = get_orders(
            account_seq=1,
            status="OPEN",
            access_token="access-token",
            symbol="AAPL",
            date_from="2026-03-01",
            date_to="2026-03-31",
            limit=20,
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(
            captured["url"],
            "https://example.test/api/v1/orders?status=OPEN&symbol=AAPL&from=2026-03-01&to=2026-03-31&limit=20",
        )
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["headers"]["X-tossinvest-account"], "1")
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(orders["orders"][0]["orderId"], "order-1")

    def test_get_order_sends_order_id_path_and_account_header(self):
        from toss.get_order import get_order

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return self._response({"result": {"orderId": "order/id", "status": "FILLED"}})

        order = get_order(
            order_id="order/id",
            account_seq=1,
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/orders/order%2Fid")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["headers"]["X-tossinvest-account"], "1")
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(order["status"], "FILLED")

    def test_order_history_scripts_can_run_directly(self):
        for script in ("src/toss/get_orders.py", "src/toss/get_order.py"):
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
