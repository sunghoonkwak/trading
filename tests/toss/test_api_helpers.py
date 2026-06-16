import io
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
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

    def test_ensure_daily_token_reissues_expired_today_token(self):
        from toss.auth import TossAuthConfig, TossToken, ensure_daily_token

        token_dir = ROOT / "tests" / ".tmp-expired-today-token"
        self.addCleanup(lambda: self._remove_tree(token_dir))
        token_dir.mkdir()
        (token_dir / "TOSS20260612_000403.json").write_text(
            json.dumps(
                {
                    "access_token": "expired-token",
                    "token_type": "Bearer",
                    "expires_in": 60,
                    "issued_at": "2026-06-12T00:04:03+00:00",
                    "expires_at": "2026-06-12T00:05:03+00:00",
                }
            ),
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
            now=datetime(2026, 6, 12, 0, 36, tzinfo=timezone.utc),
            issue_token_func=fake_issue,
        )

        self.assertEqual(calls, ["client-id"])
        self.assertEqual(token_path.name, "TOSS20260612_003600.json")
        self.assertEqual(
            json.loads(token_path.read_text(encoding="utf-8"))["access_token"],
            "new-token",
        )

    def test_load_access_token_renews_expired_token(self):
        from toss.auth import TossAuthConfig, TossToken
        from toss.auth import load_access_token

        token_dir = ROOT / "tests" / ".tmp-expired-load-token"
        self.addCleanup(lambda: self._remove_tree(token_dir))
        token_dir.mkdir()
        (token_dir / "TOSS20260612_000403.json").write_text(
            json.dumps(
                {
                    "access_token": "expired-token",
                    "token_type": "Bearer",
                    "expires_in": 86399,
                    "issued_at": "2026-06-12T00:04:03+09:00",
                    "expires_at": "2026-06-13T00:04:02+09:00",
                }
            ),
            encoding="utf-8",
        )

        def fake_issue(config):
            self.assertEqual(config.client_id, "client-id")
            return TossToken(
                access_token="renewed-token",
                token_type="Bearer",
                expires_in=86400,
            )

        access_token = load_access_token(
            token_dir=token_dir,
            config=TossAuthConfig(
                client_id="client-id",
                client_secret="client-secret",
            ),
            now=datetime(2026, 6, 13, 0, 36, tzinfo=timezone(timedelta(hours=9))),
            issue_token_func=fake_issue,
        )

        self.assertEqual(access_token, "renewed-token")
        self.assertEqual(
            json.loads((token_dir / "TOSS20260613_003600.json").read_text(
                encoding="utf-8",
            ))["access_token"],
            "renewed-token",
        )

    def _remove_tree(self, path):
        if not path.exists():
            return
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


class TossOrderApiTest(unittest.TestCase):
    def test_toss_broker_reads_usd_buying_power(self):
        from broker import toss_broker

        calls = {}

        def fake_get_buying_power(**kwargs):
            calls.update(kwargs)
            return {"cashBuyingPower": "3500.5"}

        original_load = toss_broker.load_access_token
        original_account = toss_broker.get_default_account_seq
        original_buying_power = toss_broker.get_buying_power
        try:
            toss_broker.load_access_token = lambda: "access-token"
            toss_broker.get_default_account_seq = lambda access_token: 3
            toss_broker.get_buying_power = fake_get_buying_power

            amount = toss_broker.get_orderable_usd("AAPL", 200.0)
        finally:
            toss_broker.load_access_token = original_load
            toss_broker.get_default_account_seq = original_account
            toss_broker.get_buying_power = original_buying_power

        self.assertEqual(amount, 3500.5)
        self.assertEqual(
            calls,
            {
                "account_seq": 3,
                "currency": "USD",
                "access_token": "access-token",
            },
        )

    def test_toss_broker_maps_strategy_limit_order(self):
        from broker import toss_broker
        from strategy.base import OrderSide, StrategyOrder
        from strategy.constants import ORDER_TYPE_LIMIT

        calls = {}

        def fake_create_order(**kwargs):
            calls.update(kwargs)
            return {"orderId": "order-1"}

        original_load = toss_broker.load_access_token
        original_account = toss_broker.get_default_account_seq
        original_create_order = toss_broker.create_order
        try:
            toss_broker.load_access_token = lambda: "access-token"
            toss_broker.get_default_account_seq = lambda access_token: 3
            toss_broker.create_order = fake_create_order

            success, message = toss_broker.place_order(
                StrategyOrder(
                    symbol="AAPL",
                    side=OrderSide.BUY,
                    quantity=2,
                    price=185.12,
                    order_type=ORDER_TYPE_LIMIT,
                )
            )
        finally:
            toss_broker.load_access_token = original_load
            toss_broker.get_default_account_seq = original_account
            toss_broker.create_order = original_create_order

        self.assertTrue(success)
        self.assertEqual(message, "Success")
        self.assertEqual(calls["account_seq"], 3)
        self.assertEqual(calls["access_token"], "access-token")
        self.assertEqual(calls["symbol"], "AAPL")
        self.assertEqual(calls["side"], "BUY")
        self.assertEqual(calls["order_type"], "LIMIT")
        self.assertEqual(calls["quantity"], "2")
        self.assertEqual(calls["price"], "185.12")
        self.assertNotIn("time_in_force", calls)

    def test_toss_broker_maps_strategy_loc_order(self):
        from broker import toss_broker
        from strategy.base import OrderSide, StrategyOrder
        from strategy.constants import ORDER_TYPE_LOC

        calls = {}

        original_load = toss_broker.load_access_token
        original_account = toss_broker.get_default_account_seq
        original_create_order = toss_broker.create_order
        try:
            toss_broker.load_access_token = lambda: "access-token"
            toss_broker.get_default_account_seq = lambda access_token: 3
            toss_broker.create_order = lambda **kwargs: calls.update(kwargs) or {
                "orderId": "order-1"
            }

            success, message = toss_broker.place_order(
                StrategyOrder(
                    symbol="AAPL",
                    side=OrderSide.SELL,
                    quantity=2,
                    price=190.0,
                    order_type=ORDER_TYPE_LOC,
                )
            )
        finally:
            toss_broker.load_access_token = original_load
            toss_broker.get_default_account_seq = original_account
            toss_broker.create_order = original_create_order

        self.assertTrue(success)
        self.assertEqual(message, "Success")
        self.assertEqual(calls["side"], "SELL")
        self.assertEqual(calls["order_type"], "LIMIT")
        self.assertEqual(calls["time_in_force"], "CLS")

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
    def test_request_json_waits_one_second_between_requests(self):
        from toss.client import request_json
        from toss.rate_limit import TossRateLimitManager

        clock = FakeClock()
        manager = TossRateLimitManager(
            sleep_func=clock.sleep,
            monotonic_func=clock.monotonic,
        )
        request_times = []

        def fake_urlopen(api_request, timeout):
            request_times.append(clock.monotonic())
            return _response({"result": {"ok": True}})

        api_request = request.Request(
            "https://example.test/api/v1/orders",
            method="GET",
        )

        request_json(
            api_request,
            group="ORDER",
            action_name="orders",
            timeout=10.0,
            urlopen=fake_urlopen,
            rate_limiter=manager,
        )
        request_json(
            api_request,
            group="ORDER",
            action_name="orders",
            timeout=10.0,
            urlopen=fake_urlopen,
            rate_limiter=manager,
        )

        self.assertEqual(request_times, [0.0, 1.0])
        self.assertEqual(clock.sleeps, [1.0])

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

    def test_request_json_notifies_on_final_http_failure(self):
        from toss.client import request_json
        from toss.rate_limit import TossRateLimitManager

        notifications = []
        manager = TossRateLimitManager(sleep_func=lambda _seconds: None)

        def fake_urlopen(api_request, timeout):
            raise error.HTTPError(
                api_request.full_url,
                401,
                "Unauthorized",
                {},
                io.BytesIO(b'{"error":{"code":"expired-token"}}'),
            )

        with self.assertRaisesRegex(RuntimeError, "HTTP 401"):
            request_json(
                request.Request("https://example.test/api/v1/holdings", method="GET"),
                group="ASSET",
                action_name="holdings",
                timeout=10.0,
                urlopen=fake_urlopen,
                rate_limiter=manager,
                notify_func=notifications.append,
            )

        self.assertEqual(len(notifications), 1)
        self.assertIn("Toss API query failed", notifications[0])
        self.assertIn("Group: ASSET", notifications[0])
        self.assertIn("Action: holdings", notifications[0])
        self.assertIn("expired-token", notifications[0])

    def test_request_json_sanitizes_html_http_failure(self):
        from toss.client import request_json
        from toss.rate_limit import TossRateLimitManager

        notifications = []
        manager = TossRateLimitManager(sleep_func=lambda _seconds: None)
        html_body = b"""<!DOCTYPE HTML>
<HTML><HEAD><TITLE>ERROR: The request could not be satisfied</TITLE></HEAD>
<BODY><H1>403 ERROR</H1><PRE>Request ID: abc</PRE></BODY></HTML>"""

        def fake_urlopen(api_request, timeout):
            raise error.HTTPError(
                api_request.full_url,
                403,
                "Forbidden",
                {},
                io.BytesIO(html_body),
            )

        with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
            request_json(
                request.Request(
                    "https://example.test/api/v1/buying-power?currency=USD",
                    method="GET",
                ),
                group="ORDER_INFO",
                action_name="buying-power",
                timeout=10.0,
                urlopen=fake_urlopen,
                rate_limiter=manager,
                notify_func=notifications.append,
            )

        self.assertEqual(len(notifications), 1)
        self.assertIn("non-JSON response", notifications[0])
        self.assertIn("403 ERROR", notifications[0])
        self.assertNotIn("<!DOCTYPE", notifications[0])
        self.assertNotIn("<HTML", notifications[0])

    def test_request_json_notifies_on_transport_failure(self):
        from toss.client import request_json
        from toss.rate_limit import TossRateLimitManager

        notifications = []
        manager = TossRateLimitManager(sleep_func=lambda _seconds: None)

        def fake_urlopen(api_request, timeout):
            raise error.URLError("network down")

        with self.assertRaisesRegex(RuntimeError, "network down"):
            request_json(
                request.Request("https://example.test/api/v1/holdings", method="GET"),
                group="ASSET",
                action_name="holdings",
                timeout=10.0,
                urlopen=fake_urlopen,
                rate_limiter=manager,
                notify_func=notifications.append,
            )

        self.assertEqual(len(notifications), 1)
        self.assertIn("Toss API query failed", notifications[0])
        self.assertIn("network down", notifications[0])


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
