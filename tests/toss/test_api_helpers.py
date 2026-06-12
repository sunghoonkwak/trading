import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class TossPortfolioApiTest(unittest.TestCase):
    def test_get_holdings_sends_account_header(self):
        from toss.get_holdings import get_holdings

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return _response(
                {
                    "result": {
                        "items": [
                            {
                                "symbol": "005930",
                                "name": "삼성전자",
                                "quantity": "10",
                            }
                        ]
                    }
                }
            )

        holdings = get_holdings(
            account_seq=1,
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/holdings")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["headers"]["X-tossinvest-account"], "1")
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(holdings["items"][0]["symbol"], "005930")

    def test_get_buying_power_sends_currency_and_account_header(self):
        from toss.get_buying_power import get_buying_power

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return _response(
                {"result": {"currency": "USD", "cashBuyingPower": "3500.5"}}
            )

        buying_power = get_buying_power(
            account_seq=1,
            currency="USD",
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(
            captured["url"],
            "https://example.test/api/v1/buying-power?currency=USD",
        )
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["headers"]["X-tossinvest-account"], "1")
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(buying_power["cashBuyingPower"], "3500.5")


class TossAuthTest(unittest.TestCase):
    def test_load_config_reads_credentials_file(self):
        from core.credentials import generate_key_from_password
        from cryptography.fernet import Fernet
        from toss.auth import load_config

        config_root = ROOT / "tests" / ".tmp-toss-config"
        self.addCleanup(lambda: self._remove_tree(config_root))
        config_root.mkdir(exist_ok=True)
        (config_root / "password.txt").write_text("test-password\n", encoding="utf-8")
        fernet = Fernet(generate_key_from_password("test-password"))
        (config_root / "credentials.enc").write_bytes(
            fernet.encrypt(
                b"kis-key,kis-secret,hts-id,dummy-client-id,dummy-client-secret"
            )
        )

        config = load_config(config_root=config_root)

        self.assertEqual(config.client_id, "dummy-client-id")
        self.assertEqual(config.client_secret, "dummy-client-secret")
        self.assertEqual(config.base_url, "https://openapi.tossinvest.com")

    def test_issue_token_posts_form_urlencoded_request(self):
        from toss.auth import TossAuthConfig, issue_token

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["data"] = request.data.decode("utf-8")
            captured["timeout"] = timeout
            return _response(
                {
                    "access_token": "issued-access-token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                }
            )

        token = issue_token(
            TossAuthConfig(
                client_id="client-id",
                client_secret="client-secret",
                base_url="https://example.test",
            ),
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/oauth2/token")
        self.assertEqual(
            captured["headers"]["Content-type"],
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(
            captured["data"],
            "grant_type=client_credentials&client_id=client-id&client_secret=client-secret",
        )
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(token.access_token, "issued-access-token")

    def test_ensure_daily_token_issues_after_date_changes(self):
        from toss.auth import TossAuthConfig, TossToken, ensure_daily_token

        token_dir = ROOT / "tests" / ".tmp-next-day-token"
        self.addCleanup(lambda: self._remove_tree(token_dir))
        token_dir.mkdir()
        (token_dir / "TOSS20260611_235959.json").write_text(
            '{"access_token": "yesterday-token"}\n',
            encoding="utf-8",
        )

        calls = []

        def fake_issue(config):
            calls.append(config.client_id)
            return TossToken(
                access_token="new-token",
                token_type="Bearer",
                expires_in=86400,
            )

        token_path = ensure_daily_token(
            TossAuthConfig(client_id="client-id", client_secret="client-secret"),
            token_dir=token_dir,
            now=datetime(2026, 6, 12, 0, 1, tzinfo=timezone.utc),
            issue_token_func=fake_issue,
        )

        self.assertEqual(calls, ["client-id"])
        self.assertEqual(token_path.name, "TOSS20260612_000100.json")
        self.assertEqual(
            json.loads(token_path.read_text(encoding="utf-8"))["access_token"],
            "new-token",
        )

    def _remove_tree(self, path):
        if not path.exists():
            return
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


class TossOrderApiTest(unittest.TestCase):
    def test_cancel_order_posts_empty_json_body(self):
        from toss.cancel_order import cancel_order

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _response({"result": {"orderId": "cancel-order"}})

        result = cancel_order(
            order_id="modified/order",
            account_seq=1,
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(
            captured["url"],
            "https://example.test/api/v1/orders/modified%2Forder/cancel",
        )
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["headers"]["X-tossinvest-account"], "1")
        self.assertEqual(captured["headers"]["Content-type"], "application/json")
        self.assertEqual(captured["body"], {})
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(result["orderId"], "cancel-order")

    def test_get_orders_sends_open_order_filters(self):
        from toss.get_orders import get_orders

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return _response(
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
            limit=20,
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(
            captured["url"],
            "https://example.test/api/v1/orders?status=OPEN&symbol=AAPL&limit=20",
        )
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["headers"]["X-tossinvest-account"], "1")
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(orders["orders"][0]["orderId"], "order-1")


class TossRateLimitTest(unittest.TestCase):
    def test_request_json_retries_429_after_retry_after(self):
        from toss.client import request_json
        from toss.rate_limit import TossRateLimitManager

        clock = FakeClock()
        manager = TossRateLimitManager(
            sleep_func=clock.sleep,
            monotonic_func=clock.monotonic,
            jitter_func=lambda _start, _end: 0.0,
        )
        calls = []

        def fake_urlopen(api_request, timeout):
            calls.append((api_request.full_url, timeout))
            if len(calls) == 1:
                raise error.HTTPError(
                    api_request.full_url,
                    429,
                    "Too Many Requests",
                    {"Retry-After": "2"},
                    None,
                )
            return _response({"result": {"ok": True}})

        payload = request_json(
            request.Request("https://example.test/api/v1/orders", method="GET"),
            group="ORDER",
            action_name="orders",
            timeout=10.0,
            urlopen=fake_urlopen,
            rate_limiter=manager,
            max_retries=1,
        )

        self.assertEqual(payload["result"], {"ok": True})
        self.assertEqual(len(calls), 2)
        self.assertEqual(clock.sleeps, [2.0])


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def _response(payload):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    return FakeResponse()
