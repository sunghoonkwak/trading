import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class OrderActionsTest(unittest.TestCase):
    def test_create_order_posts_json_body_and_account_header(self):
        from toss.create_order import create_order

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return self._response({"result": {"orderId": "created-order", "clientOrderId": "client-1"}})

        result = create_order(
            account_seq=1,
            access_token="access-token",
            symbol="QQQM",
            side="BUY",
            order_type="LIMIT",
            quantity="1",
            price="230.00",
            client_order_id="client-1",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/orders")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["headers"]["X-tossinvest-account"], "1")
        self.assertEqual(captured["headers"]["Content-type"], "application/json")
        self.assertEqual(
            captured["body"],
            {
                "symbol": "QQQM",
                "side": "BUY",
                "orderType": "LIMIT",
                "quantity": "1",
                "price": "230.00",
                "clientOrderId": "client-1",
            },
        )
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(result["orderId"], "created-order")

    def test_modify_order_posts_price_only_for_us_limit_order(self):
        from toss.modify_order import modify_order

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return self._response({"result": {"orderId": "modified-order"}})

        result = modify_order(
            order_id="created/order",
            account_seq=1,
            access_token="access-token",
            order_type="LIMIT",
            price="260.00",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/orders/created%2Forder/modify")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["headers"]["X-tossinvest-account"], "1")
        self.assertEqual(captured["headers"]["Content-type"], "application/json")
        self.assertEqual(captured["body"], {"orderType": "LIMIT", "price": "260.00"})
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(result["orderId"], "modified-order")

    def test_cancel_order_posts_empty_json_body(self):
        from toss.cancel_order import cancel_order

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return self._response({"result": {"orderId": "cancel-order"}})

        result = cancel_order(
            order_id="modified/order",
            account_seq=1,
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/orders/modified%2Forder/cancel")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["headers"]["X-tossinvest-account"], "1")
        self.assertEqual(captured["headers"]["Content-type"], "application/json")
        self.assertEqual(captured["body"], {})
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(result["orderId"], "cancel-order")

    def test_order_action_scripts_can_run_directly(self):
        scripts = (
            "src/toss/create_order.py",
            "src/toss/modify_order.py",
            "src/toss/cancel_order.py",
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
