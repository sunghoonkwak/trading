import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from strategy import execution_service
from strategy.base import OrderSide, StrategyOrder


def _buy_order():
    return StrategyOrder(
        symbol="TQQQ",
        side=OrderSide.BUY,
        quantity=10,
        price=100.0,
        reason="Buy Normal",
    )


def test_prepare_cash_funding_uses_pending_raoeo_orders(monkeypatch):
    report = {"pending_orders": [_buy_order()]}
    requested = []
    monkeypatch.setattr(
        execution_service,
        "get_orderable_usd",
        lambda symbol, price: requested.append((symbol, price)) or 100.0,
    )
    monkeypatch.setattr(
        execution_service,
        "get_market_data",
        lambda force_refresh=False, include_cash_ticker=False: (
            {"BIL": {"qty": 20, "cur_price": 100.0}},
            {"BIL": 100.0},
        ),
    )
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: {"cash_ticker": "BIL"},
    )

    order, info = execution_service.prepare_raoeo_cash_funding(report)

    assert info["required"] is True
    assert info["orderable_usd"] == 100.0
    assert order.symbol == "BIL"
    assert order.quantity == 10
    assert requested == [("TQQQ", 100.0)]


def test_execute_cash_funding_does_not_submit_strategy_orders_on_failure(monkeypatch):
    funding_order = StrategyOrder(
        symbol="BIL",
        side=OrderSide.SELL,
        quantity=10,
        price=99.0,
        reason="Fund RAOEO Buys",
    )
    monkeypatch.setattr(
        execution_service,
        "prepare_raoeo_cash_funding",
        lambda report=None: (funding_order, {"required": True}),
    )
    monkeypatch.setattr(
        execution_service,
        "execute_single_order",
        lambda order: (False, "rejected"),
    )
    slept = []
    monkeypatch.setattr(execution_service.time, "sleep", lambda seconds: slept.append(seconds))

    result, info = execution_service.execute_raoeo_cash_funding()

    assert result["success"] is False
    assert result["order"] is funding_order
    assert slept == []


def test_execute_cash_funding_waits_five_seconds_after_success(monkeypatch):
    funding_order = StrategyOrder(
        symbol="BIL",
        side=OrderSide.SELL,
        quantity=10,
        price=99.0,
        reason="Fund RAOEO Buys",
    )
    monkeypatch.setattr(
        execution_service,
        "prepare_raoeo_cash_funding",
        lambda report=None: (funding_order, {"required": True}),
    )
    monkeypatch.setattr(
        execution_service,
        "execute_single_order",
        lambda order: (True, "Success"),
    )
    slept = []
    monkeypatch.setattr(execution_service.time, "sleep", lambda seconds: slept.append(seconds))

    result, info = execution_service.execute_raoeo_cash_funding()

    assert result["success"] is True
    assert slept == [5]


def test_execute_orders_runs_strategy_sells_before_buys(monkeypatch):
    buy_one = StrategyOrder("TQQQ", OrderSide.BUY, 1, 100.0, "buy one")
    sell_one = StrategyOrder("SOXL", OrderSide.SELL, 2, 50.0, "sell one")
    buy_two = StrategyOrder("SCHD", OrderSide.BUY, 3, 30.0, "buy two")
    sell_two = StrategyOrder("UPRO", OrderSide.SELL, 4, 40.0, "sell two")
    submitted = []
    slept = []

    monkeypatch.setattr(
        execution_service,
        "execute_single_order",
        lambda order: submitted.append(order.symbol) or (True, "Success"),
    )
    monkeypatch.setattr(execution_service.time, "sleep", lambda seconds: slept.append(seconds))

    execution_service._execute_orders(
        [buy_one, sell_one, buy_two, sell_two],
        sell_first=True,
        sell_wait_seconds=5,
    )

    assert submitted == ["SOXL", "UPRO", "TQQQ", "SCHD"]
    assert slept == [5]


def test_cash_funding_results_are_stored_separately_from_retry_orders(monkeypatch):
    saved = {}
    monkeypatch.setattr(
        execution_service,
        "_load_history",
        lambda: [{"date": "2026-05-27", "raoeo": {"orders": []}}],
    )
    monkeypatch.setattr(
        execution_service,
        "save_json",
        lambda file_type, data: saved.setdefault("history", data),
    )
    result = {
        "order": StrategyOrder("BIL", OrderSide.SELL, 2, 99.0, "cash funding"),
        "success": False,
        "message": "rejected",
    }

    execution_service.save_raoeo_cash_funding_result("2026-05-27", result)

    raoeo_history = saved["history"][0]["raoeo"]
    assert raoeo_history["orders"] == []
    assert raoeo_history["cash_funding_results"][0]["ticker"] == "BIL"
    assert raoeo_history["cash_funding_results"][0]["success"] is False


def test_strategy_history_update_preserves_manual_cash_funding_results(monkeypatch):
    existing_funding = [{"ticker": "BIL", "success": True}]
    saved = {}
    monkeypatch.setattr(
        execution_service,
        "_load_history",
        lambda: [{
            "date": "2026-05-27",
            "raoeo": {
                "orders": [],
                "cash_funding_results": existing_funding,
            },
        }],
    )
    monkeypatch.setattr(
        execution_service,
        "save_json",
        lambda file_type, data: saved.setdefault("history", data),
    )

    execution_service._save_strategy_to_history(
        "2026-05-27",
        "raoeo",
        {"orders": [{"ticker": "TQQQ"}]},
    )

    assert (
        saved["history"][0]["raoeo"]["cash_funding_results"]
        == existing_funding
    )
