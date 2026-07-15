import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))


class _Response:
    def __init__(self, payload: object, status: int = 200):
        self._body = json.dumps(payload).encode("utf-8") if payload is not None else b""
        self.status = status
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


def test_get_rankings_builds_validated_query():
    from infrastructure.toss.get_rankings import get_rankings

    captured = {}

    def fake_urlopen(api_request, timeout):
        captured["url"] = api_request.full_url
        captured["timeout"] = timeout
        return _Response({"result": {"rankings": []}})

    result = get_rankings(
        ranking_type="market_trading_amount",
        market_country="kr",
        duration="realtime",
        exclude_investment_caution=True,
        count=10,
        access_token="token",
        base_url="https://example.test",
        urlopen=fake_urlopen,
    )

    assert result == {"rankings": []}
    assert captured["url"] == (
        "https://example.test/api/v1/rankings?type=MARKET_TRADING_AMOUNT&"
        "marketCountry=KR&duration=realtime&excludeInvestmentCaution=true&count=10"
    )
    with pytest.raises(ValueError, match="do not support realtime"):
        get_rankings(
            ranking_type="TOP_GAINERS",
            market_country="KR",
            duration="realtime",
            access_token="token",
        )


def test_market_indicator_helpers_build_queries():
    from infrastructure.toss.get_market_indicators import (
        get_market_indicator_candles,
        get_market_indicator_investor_trading,
        get_market_indicator_prices,
    )

    urls = []

    def fake_urlopen(api_request, timeout):
        urls.append(api_request.full_url)
        return _Response({"result": [] if "prices" in api_request.full_url else {"items": []}})

    assert (
        get_market_indicator_prices(
            ["KOSPI", "KR_BOND_3Y"],
            access_token="token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )
        == []
    )
    assert get_market_indicator_candles(
        symbol="KOSPI",
        interval="1m",
        count=2,
        before="2026-01-01T09:00:00+09:00",
        access_token="token",
        base_url="https://example.test",
        urlopen=fake_urlopen,
    ) == {"items": []}
    assert get_market_indicator_investor_trading(
        symbol="KOSDAQ",
        interval="1d",
        count=2,
        until="2026-01-01",
        access_token="token",
        base_url="https://example.test",
        urlopen=fake_urlopen,
    ) == {"items": []}

    assert urls == [
        "https://example.test/api/v1/market-indicators/prices?symbols=KOSPI%2CKR_BOND_3Y",
        "https://example.test/api/v1/market-indicators/KOSPI/candles?interval=1m&count=2&before=2026-01-01T09%3A00%3A00%2B09%3A00",
        "https://example.test/api/v1/market-indicators/KOSDAQ/investor-trading?interval=1d&count=2&until=2026-01-01",
    ]
    with pytest.raises(ValueError, match="only 1d"):
        get_market_indicator_candles(symbol="KR_BOND_3Y", interval="1m", access_token="token")


def test_create_conditional_order_posts_validated_body():
    from infrastructure.toss.conditional_orders import create_conditional_order

    captured = {}

    def fake_urlopen(api_request, timeout):
        captured["url"] = api_request.full_url
        captured["headers"] = dict(api_request.header_items())
        captured["body"] = json.loads(api_request.data)
        return _Response({"result": {"conditionalOrderId": "created"}})

    result = create_conditional_order(
        account_seq=7,
        access_token="token",
        symbol="005930",
        conditional_type="OCO",
        quantity="10",
        order_type="LIMIT",
        expire_date="2026-12-31",
        first={"orderSide": "SELL", "triggerPrice": "100", "orderPrice": "100"},
        second={"orderSide": "SELL", "triggerPrice": "90", "orderPrice": "90"},
        client_order_id="idempotency-key",
        base_url="https://example.test",
        urlopen=fake_urlopen,
    )

    assert result == {"conditionalOrderId": "created"}
    assert captured["url"] == "https://example.test/api/v1/conditional-orders"
    assert captured["headers"]["X-tossinvest-account"] == "7"
    assert captured["body"]["type"] == "OCO"
    assert captured["body"]["second"]["orderSide"] == "SELL"


def test_conditional_order_validates_type_rules():
    from infrastructure.toss.conditional_orders import create_conditional_order

    with pytest.raises(ValueError, match="require LIMIT"):
        create_conditional_order(
            account_seq=7,
            access_token="token",
            symbol="005930",
            conditional_type="OCO",
            quantity="10",
            order_type="MARKET",
            expire_date="2026-12-31",
            first={"orderSide": "SELL", "triggerPrice": "100"},
            second={"orderSide": "SELL", "triggerPrice": "90"},
        )
    with pytest.raises(ValueError, match="BUY then SELL"):
        create_conditional_order(
            account_seq=7,
            access_token="token",
            symbol="005930",
            conditional_type="OTO",
            quantity="10",
            order_type="LIMIT",
            expire_date="2026-12-31",
            first={"orderSide": "SELL", "triggerPrice": "100", "orderPrice": "100"},
            second={"orderSide": "SELL", "triggerPrice": "90", "orderPrice": "90"},
        )


def test_conditional_order_read_modify_and_cancel_requests():
    from infrastructure.toss.conditional_orders import (
        cancel_conditional_order,
        get_conditional_order,
        get_conditional_orders,
        modify_conditional_order,
    )

    requests = []

    def fake_urlopen(api_request, timeout):
        requests.append((api_request.method, api_request.full_url, api_request.data))
        if api_request.method == "DELETE":
            return _Response(None, status=204)
        return _Response({"result": {"conditionalOrderId": "next"}})

    kwargs = {
        "account_seq": 7,
        "access_token": "token",
        "base_url": "https://example.test",
        "urlopen": fake_urlopen,
    }
    assert get_conditional_orders(status="OPEN", symbol="AAPL", limit=20, **kwargs) == {
        "conditionalOrderId": "next"
    }
    assert get_conditional_order(conditional_order_id="a/b", **kwargs) == {
        "conditionalOrderId": "next"
    }
    assert modify_conditional_order(
        conditional_order_id="old",
        conditional_type="SINGLE",
        quantity="1",
        order_type="MARKET",
        expire_date="2026-12-31",
        first={"orderSide": "BUY", "triggerPrice": "100"},
        **kwargs,
    ) == {"conditionalOrderId": "next"}
    assert cancel_conditional_order(conditional_order_id="old", **kwargs) is None

    assert [item[:2] for item in requests] == [
        ("GET", "https://example.test/api/v1/conditional-orders?status=OPEN&symbol=AAPL&limit=20"),
        ("GET", "https://example.test/api/v1/conditional-orders/a%2Fb"),
        ("POST", "https://example.test/api/v1/conditional-orders/old/modify"),
        ("DELETE", "https://example.test/api/v1/conditional-orders/old"),
    ]
