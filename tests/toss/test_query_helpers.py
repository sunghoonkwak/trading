import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


@pytest.mark.parametrize(
    ("interval", "count", "message"),
    [
        ("5m", None, "interval"),
        ("1m", 0, "count"),
        ("1d", 201, "count"),
    ],
)
def test_get_candles_validates_interval_and_count(interval, count, message):
    from infrastructure.toss.get_candles import get_candles

    with pytest.raises(ValueError, match=message):
        get_candles(
            symbol="AAPL",
            interval=interval,
            count=count,
            access_token="token",
        )


def test_get_candles_builds_all_query_options(monkeypatch):
    from infrastructure.toss import get_candles

    captured = {}

    def fake_get_payload(**kwargs):
        captured.update(kwargs)
        return {"items": []}

    monkeypatch.setattr(get_candles, "_get_payload", fake_get_payload)

    result = get_candles.get_candles(
        symbol=" AAPL ",
        interval="1d",
        count=20,
        before="2026-07-09T00:00:00Z",
        adjusted=False,
        access_token="token",
        base_url="https://example.test/",
    )

    assert result == {"items": []}
    assert captured["url"] == (
        "https://example.test/api/v1/candles?"
        "symbol=AAPL&interval=1d&count=20&"
        "before=2026-07-09T00%3A00%3A00Z&adjusted=false"
    )
    assert captured["group"] == "MARKET_DATA_CHART"


@pytest.mark.parametrize(
    ("module_name", "function_name", "country"),
    [
        ("infrastructure.toss.get_kr_market_calendar", "get_kr_market_calendar", "KR"),
        ("infrastructure.toss.get_us_market_calendar", "get_us_market_calendar", "US"),
    ],
)
def test_market_calendar_builds_optional_date(
    monkeypatch,
    module_name,
    function_name,
    country,
):
    module = __import__(module_name, fromlist=[function_name])
    captured = {}
    monkeypatch.setattr(
        module,
        "_get_result_object",
        lambda **kwargs: captured.update(kwargs) or {"days": []},
    )

    result = getattr(module, function_name)(
        access_token="token",
        date="2026-07-09",
        base_url="https://example.test/",
    )

    assert result == {"days": []}
    assert captured["url"] == (
        f"https://example.test/api/v1/market-calendar/{country}"
        "?date=2026-07-09"
    )
    assert captured["group"] == "MARKET_INFO"


@pytest.mark.parametrize(
    ("count", "message"),
    [(0, "between 1 and 50"), (51, "between 1 and 50")],
)
def test_get_trades_validates_count(count, message):
    from infrastructure.toss.get_trades import get_trades

    with pytest.raises(ValueError, match=message):
        get_trades(symbol="AAPL", count=count, access_token="token")


def test_get_trades_builds_query(monkeypatch):
    from infrastructure.toss import get_trades

    captured = {}
    monkeypatch.setattr(
        get_trades,
        "_get_payload",
        lambda **kwargs: captured.update(kwargs) or [{"price": "200"}],
    )

    result = get_trades.get_trades(
        symbol=" AAPL ",
        count=50,
        access_token="token",
        base_url="https://example.test",
    )

    assert result == [{"price": "200"}]
    assert captured["url"].endswith("/api/v1/trades?symbol=AAPL&count=50")
    assert captured["result_type"] is list


def test_get_price_limit_builds_query(monkeypatch):
    from infrastructure.toss import get_price_limit

    captured = {}
    monkeypatch.setattr(
        get_price_limit,
        "_get_payload",
        lambda **kwargs: captured.update(kwargs) or {"upper": "300"},
    )

    result = get_price_limit.get_price_limit(
        symbol=" AAPL ",
        access_token="token",
        base_url="https://example.test/",
    )

    assert result == {"upper": "300"}
    assert captured["url"] == (
        "https://example.test/api/v1/price-limits?symbol=AAPL"
    )
    assert captured["group"] == "MARKET_DATA"


def test_get_commissions_builds_account_request(monkeypatch):
    from infrastructure.toss import get_commissions

    captured = {}

    def fake_request_json(api_request, **kwargs):
        captured["request"] = api_request
        captured.update(kwargs)
        return {"result": [{"market": "US"}]}

    monkeypatch.setattr(get_commissions, "request_json", fake_request_json)

    result = get_commissions.get_commissions(
        account_seq=7,
        access_token="token",
        base_url="https://example.test/",
    )

    assert result == [{"market": "US"}]
    assert captured["request"].full_url.endswith("/api/v1/commissions")
    assert captured["request"].headers["X-tossinvest-account"] == "7"
    assert captured["group"] == "ORDER_INFO"


def test_get_commissions_rejects_missing_result(monkeypatch):
    from infrastructure.toss import get_commissions

    monkeypatch.setattr(
        get_commissions,
        "request_json",
        lambda *_args, **_kwargs: {"result": {}},
    )

    with pytest.raises(RuntimeError, match="result list"):
        get_commissions.get_commissions(
            account_seq=7,
            access_token="token",
        )


def test_get_order_encodes_id_and_builds_account_request(monkeypatch):
    from infrastructure.toss import get_order

    captured = {}

    def fake_request_json(api_request, **kwargs):
        captured["request"] = api_request
        captured.update(kwargs)
        return {"result": {"id": "order/id"}}

    monkeypatch.setattr(get_order, "request_json", fake_request_json)

    result = get_order.get_order(
        order_id=" order/id ",
        account_seq=3,
        access_token="token",
        base_url="https://example.test",
    )

    assert result == {"id": "order/id"}
    assert captured["request"].full_url.endswith("/api/v1/orders/order%2Fid")
    assert captured["request"].headers["X-tossinvest-account"] == "3"
    assert captured["group"] == "ORDER_HISTORY"


def test_get_order_validates_id_and_result(monkeypatch):
    from infrastructure.toss import get_order

    with pytest.raises(ValueError, match="order_id"):
        get_order.get_order(
            order_id=" ",
            account_seq=3,
            access_token="token",
        )

    monkeypatch.setattr(
        get_order,
        "request_json",
        lambda *_args, **_kwargs: {"result": []},
    )
    with pytest.raises(RuntimeError, match="result object"):
        get_order.get_order(
            order_id="id",
            account_seq=3,
            access_token="token",
        )


def test_get_sellable_quantity_builds_request_and_validates(monkeypatch):
    from infrastructure.toss import get_sellable_quantity

    captured = {}

    def fake_request_json(api_request, **kwargs):
        captured["request"] = api_request
        captured.update(kwargs)
        return {"result": {"quantity": "5"}}

    monkeypatch.setattr(
        get_sellable_quantity,
        "request_json",
        fake_request_json,
    )

    result = get_sellable_quantity.get_sellable_quantity(
        account_seq=9,
        symbol=" AAPL ",
        access_token="token",
        base_url="https://example.test",
    )

    assert result == {"quantity": "5"}
    assert captured["request"].full_url.endswith(
        "/api/v1/sellable-quantity?symbol=AAPL",
    )
    assert captured["request"].headers["X-tossinvest-account"] == "9"

    with pytest.raises(ValueError, match="symbol"):
        get_sellable_quantity.get_sellable_quantity(
            account_seq=9,
            symbol=" ",
            access_token="token",
        )


def test_get_sellable_quantity_rejects_missing_result(monkeypatch):
    from infrastructure.toss import get_sellable_quantity

    monkeypatch.setattr(
        get_sellable_quantity,
        "request_json",
        lambda *_args, **_kwargs: {"result": []},
    )

    with pytest.raises(RuntimeError, match="result object"):
        get_sellable_quantity.get_sellable_quantity(
            account_seq=9,
            symbol="AAPL",
            access_token="token",
        )


def test_modify_order_normalizes_body_and_encodes_id(monkeypatch):
    from infrastructure.toss import modify_order

    captured = {}
    monkeypatch.setattr(
        modify_order,
        "_post_order_action",
        lambda **kwargs: captured.update(kwargs) or {"id": "changed"},
    )

    result = modify_order.modify_order(
        order_id=" order/id ",
        account_seq=2,
        access_token="token",
        order_type="limit",
        quantity="3",
        price="200",
        confirm_high_value_order=True,
        base_url="https://example.test/",
    )

    assert result == {"id": "changed"}
    assert captured["url"].endswith("/api/v1/orders/order%2Fid/modify")
    assert captured["body"] == {
        "orderType": "LIMIT",
        "quantity": "3",
        "price": "200",
        "confirmHighValueOrder": True,
    }
