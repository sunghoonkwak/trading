import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from strategy import raoeo
from strategy.base import OrderSide, StrategyStatus
from strategy.constants import ORDER_TYPE_LIMIT, ORDER_TYPE_LOC


def _targets_config():
    return {
        "TQQQ": {
            "seed": 1000,
            "duration": 1,
            "phase": [
                {
                    "name": "initial",
                    "threshold": 1.0,
                    "buy": [{"type": "normal", "ratio": 1.0}],
                    "sell": [],
                }
            ],
        }
    }


def _portfolio(cash_ticker_qty=100):
    return {
        "BIL": {"qty": cash_ticker_qty, "avg_price": 100.0, "cur_price": 100.0},
    }


def _calculate(cash_ticker_qty=100):
    orders, _ = raoeo.calculate_orders(
        targets_config=_targets_config(),
        portfolio=_portfolio(cash_ticker_qty=cash_ticker_qty),
        current_prices={"TQQQ": 100.0, "BIL": 100.0},
    )
    return orders


def _cash_funding(orderable_usd=0.0, cash_ticker_qty=100):
    return raoeo.calculate_cash_funding_order(
        orders=_calculate(cash_ticker_qty=cash_ticker_qty),
        portfolio=_portfolio(cash_ticker_qty=cash_ticker_qty),
        current_prices={"TQQQ": 100.0, "BIL": 100.0},
        cash_ticker="BIL",
        orderable_usd=orderable_usd,
    )


def _target_config(ticker, seed, duration, buy_rules, sell_profit=0.06):
    return {
        ticker: {
            "seed": seed,
            "duration": duration,
            "phase": [
                {
                    "name": "defensive",
                    "buy": buy_rules,
                    "sell": [{"type": "Limit", "ratio": 0.0, "profit": sell_profit}],
                }
            ],
        }
    }


def _fas_holding():
    return {"FAS": {"qty": 20, "avg_price": 133.99, "cur_price": 134.0}}


def _buy_orders(orders):
    return [order for order in orders if order.side == OrderSide.BUY]


def _successful_buy_history(ticker, qty, price, reason, target_budget):
    return [
        {
            "date": "2026-06-10",
            "raoeo": {
                "orders": [
                    {
                        "ticker": ticker,
                        "side": "BUY",
                        "qty": qty,
                        "price": price,
                        "reason": reason,
                        "success": True,
                        "target_budget": target_budget,
                    },
                ],
            },
        },
    ]


def test_standard_orders_do_not_automatically_sell_cash_ticker():
    orders = _calculate()

    cash_sales = [
        order for order in orders
        if order.symbol == "BIL" and order.side == OrderSide.SELL
    ]

    assert cash_sales == []


def test_raoeo_uses_broker_neutral_order_types():
    orders, _ = raoeo.calculate_orders(
        targets_config={
            "TQQQ": {
                "seed": 1000,
                "duration": 1,
                "phase": [
                    {
                        "name": "initial",
                        "threshold": 1.0,
                        "buy": [{"type": "normal", "ratio": 1.0}],
                        "sell": [
                            {"type": "Limit", "ratio": 0.5, "profit": 0.1},
                            {"type": "LOC", "ratio": 0.5, "profit": 0.2},
                        ],
                    }
                ],
            }
        },
        portfolio={"TQQQ": {"qty": 10, "avg_price": 100.0, "cur_price": 100.0}},
        current_prices={"TQQQ": 100.0},
    )

    sell_orders = [order for order in orders if order.side == OrderSide.SELL]
    buy_orders = [order for order in orders if order.side == OrderSide.BUY]

    assert [order.order_type for order in sell_orders] == [
        ORDER_TYPE_LIMIT,
        ORDER_TYPE_LOC,
    ]
    assert buy_orders[0].order_type == ORDER_TYPE_LOC


def test_cash_funding_sell_uses_full_buy_budget_without_orderable_usd():
    cash_sell, info = _cash_funding()

    assert cash_sell.quantity == 10
    assert cash_sell.price == 99.0
    assert cash_sell.order_type == ORDER_TYPE_LIMIT
    assert info["required"] is True


def test_cash_funding_sell_only_funds_shortfall_after_orderable_usd():
    cash_sell, info = _cash_funding(orderable_usd=500.0)

    assert cash_sell.quantity == 5
    assert "$989.91" in cash_sell.reason
    assert "$500.00" in cash_sell.reason
    assert "$489.91" in cash_sell.reason
    assert info["shortfall"] == 489.91


def test_cash_funding_sell_is_skipped_when_orderable_usd_covers_buys():
    cash_sell, info = _cash_funding(orderable_usd=1000.0)

    assert cash_sell is None
    assert info["required"] is False


def test_cash_funding_fails_when_holding_cannot_cover_shortfall():
    cash_sell, info = _cash_funding(cash_ticker_qty=3)

    assert cash_sell is None
    assert info["required"] is True
    assert "Insufficient" in info["error"]


def test_successful_buy_reuses_unspent_budget_next_day():
    targets_config = _target_config(
        "SOXL",
        seed=1000,
        duration=1,
        buy_rules=[{"type": "normal", "ratio": 1.0}],
        sell_profit=0.1,
    )
    history_data = _successful_buy_history(
        "SOXL",
        qty=3,
        price=266.63,
        reason="Buy Normal",
        target_budget=1000.0,
    )

    orders, info = raoeo.calculate_orders(
        targets_config=targets_config,
        portfolio={"SOXL": {"qty": 1, "avg_price": 242.4, "cur_price": 240.0}},
        current_prices={"SOXL": 240.0},
        history_data=history_data,
        today_date="2026-06-02",
    )

    buy_order = _buy_orders(orders)[0]
    assert buy_order.quantity == 4
    assert buy_order.target_budget == 1200.11
    assert info["ticker_info"]["SOXL"]["budget_carryover"] == 200.11


def test_skipped_buy_budget_returns_to_next_day_budget_pool():
    targets_config = _target_config(
        "FAS",
        seed=10000,
        duration=60,
        buy_rules=[{"type": "normal", "ratio": 1.0, "price_percent_cap": 0.06}],
    )
    history_data = [
        {
            "date": "2026-06-10",
            "raoeo": {
                "orders": [],
                "skipped_buy_budgets": {"FAS": 83.33},
            },
        }
    ]

    orders, info = raoeo.calculate_orders(
        targets_config=targets_config,
        portfolio=_fas_holding(),
        current_prices={"FAS": 134.0},
        history_data=history_data,
        today_date="2026-06-11",
    )

    buy_orders = _buy_orders(orders)

    assert [(order.reason, order.quantity) for order in buy_orders] == [
        ("Buy Normal", 1),
    ]
    assert buy_orders[0].target_budget == 250.0
    assert info["ticker_info"]["FAS"]["budget_carryover"] == 83.33


import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

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


def test_get_market_data_uses_configured_broker_as_portfolio_scope(monkeypatch):
    requested = []

    monkeypatch.setattr(
        execution_service.strategy_broker,
        "get_strategy_broker_name",
        lambda: "toss",
    )
    monkeypatch.setattr(
        "data.data_service.get_portfolio_data",
        lambda force_refresh=False, scope="all": requested.append(
            (force_refresh, scope)
        ) or {"merged_data": {"AAPL": {"qty": 2, "cur_price": 160.0}}},
    )
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: {
            "raoeo": {"targets": {}},
            "value_averaging": {"targets": {}},
            "rebalancing": {"assets": []},
        },
    )

    holdings, prices = execution_service.get_market_data(force_refresh=True)

    assert holdings == {"AAPL": {"qty": 2, "cur_price": 160.0}}
    assert prices == {}
    assert requested == [(True, "toss")]


def test_get_market_data_uses_holding_price_before_rest_price(monkeypatch):
    monkeypatch.setattr(
        execution_service.strategy_broker,
        "get_strategy_broker_name",
        lambda: "toss",
    )
    monkeypatch.setattr(
        "data.data_service.get_portfolio_data",
        lambda force_refresh=False, scope="all": {
            "merged_data": {"AAPL": {"qty": 2, "cur_price": 160.0}},
        },
    )
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: {
            "raoeo": {"targets": {"AAPL": {"enabled": True}}},
            "value_averaging": {"targets": {}},
            "rebalancing": {"assets": []},
        },
    )
    monkeypatch.setattr(
        execution_service.market_data,
        "fetch_price",
        lambda ticker: (_ for _ in ()).throw(
            AssertionError("holding cur_price should avoid REST price lookup")
        ),
    )

    holdings, prices = execution_service.get_market_data(force_refresh=True)

    assert holdings == {"AAPL": {"qty": 2, "cur_price": 160.0}}
    assert prices == {"AAPL": 160.0}


def test_get_market_data_fetches_missing_prices_in_batch(monkeypatch):
    requested = []
    monkeypatch.setattr(
        execution_service.strategy_broker,
        "get_strategy_broker_name",
        lambda: "toss",
    )
    monkeypatch.setattr(
        "data.data_service.get_portfolio_data",
        lambda force_refresh=False, scope="all": {
            "merged_data": {"AAPL": {"qty": 2, "cur_price": 0.0}},
        },
    )
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: {
            "raoeo": {"targets": {"AAPL": {"enabled": True}}},
            "value_averaging": {"targets": {"MSFT": {"enabled": True}}},
            "rebalancing": {"assets": []},
        },
    )
    monkeypatch.setattr(
        execution_service.market_data,
        "fetch_prices",
        lambda tickers: requested.append(set(tickers)) or {
            "AAPL": 160.0,
            "MSFT": 420.0,
        },
    )
    monkeypatch.setattr(
        execution_service.market_data,
        "fetch_price",
        lambda ticker: (_ for _ in ()).throw(
            AssertionError("single KIS price lookup should not be used first")
        ),
    )

    holdings, prices = execution_service.get_market_data(force_refresh=True)

    assert holdings == {"AAPL": {"qty": 2, "cur_price": 0.0}}
    assert prices == {"AAPL": 160.0, "MSFT": 420.0}
    assert requested == [{"AAPL", "MSFT"}]


def test_prepare_cash_funding_reuses_report_market_data(monkeypatch):
    report = {
        "pending_orders": [_buy_order()],
        "info": {
            "holdings": {"BIL": {"qty": 20, "cur_price": 100.0}},
            "current_prices": {"BIL": 100.0},
        },
    }
    monkeypatch.setattr(
        execution_service,
        "get_orderable_usd",
        lambda symbol, price: 100.0,
    )
    monkeypatch.setattr(
        execution_service,
        "get_market_data",
        lambda force_refresh=False, include_cash_ticker=False: (_ for _ in ()).throw(
            AssertionError("report market data should be reused")
        ),
    )
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: {"cash_ticker": "BIL"},
    )

    order, info = execution_service.prepare_raoeo_cash_funding(report)

    assert info["required"] is True
    assert order.symbol == "BIL"


def test_prepare_cash_funding_reuses_toss_usd_cash_as_orderable_usd(monkeypatch):
    report = {
        "pending_orders": [_buy_order()],
        "info": {
            "holdings": {
                "BIL": {"qty": 20, "cur_price": 100.0},
                "USD cash": {"type": "CASH", "qty": 100.0},
            },
            "current_prices": {"BIL": 100.0},
        },
    }
    monkeypatch.setattr(
        execution_service.strategy_broker,
        "get_strategy_broker_name",
        lambda: "toss",
    )
    monkeypatch.setattr(
        execution_service,
        "get_orderable_usd",
        lambda symbol, price: (_ for _ in ()).throw(
            AssertionError("Toss USD cash should avoid a second buying-power call")
        ),
    )
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: {"cash_ticker": "BIL"},
    )

    order, info = execution_service.prepare_raoeo_cash_funding(report)

    assert info["orderable_usd"] == 100.0
    assert order.symbol == "BIL"


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


def test_execute_single_order_logs_audit_before_broker_submission(monkeypatch, caplog):
    order = StrategyOrder(
        symbol="SOXL",
        side=OrderSide.BUY,
        quantity=3,
        price=12.5,
        order_type=ORDER_TYPE_LOC,
        reason="Buy Normal",
    )
    calls = []

    monkeypatch.setattr(
        execution_service.strategy_broker,
        "get_strategy_broker_name",
        lambda: "toss",
    )

    def place_order(submitted_order):
        calls.append(("place_order", submitted_order))
        assert "Preparing strategy order" in caplog.text
        assert "broker=toss" in caplog.text
        assert "symbol=SOXL" in caplog.text
        assert "side=BUY" in caplog.text
        assert "quantity=3" in caplog.text
        assert "price=12.50" in caplog.text
        assert "estimated_amount=37.50" in caplog.text
        return True, "Success"

    monkeypatch.setattr(execution_service.strategy_broker, "place_order", place_order)

    caplog.set_level("INFO")

    assert execution_service.execute_single_order(order) == (True, "Success")
    assert calls == [("place_order", order)]


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


def test_run_raoeo_persists_skipped_buy_budget_history(monkeypatch):
    saved = {}
    config = {
        "raoeo": {
            "enabled": True,
            "targets": {
                "FAS": {
                    "enabled": True,
                    "seed": 10000,
                    "duration": 60,
                    "phase": [{"name": "defensive", "buy": [], "sell": []}],
                }
            },
        }
    }
    monkeypatch.setattr(
        execution_service,
        "_get_market_status",
        lambda today: {"is_market_open": True, "is_holiday": False, "message": ""},
    )
    monkeypatch.setattr(
        execution_service.strategy_broker,
        "get_strategy_broker_name",
        lambda: "toss",
    )
    monkeypatch.setattr(execution_service, "_load_history", lambda: [])
    monkeypatch.setattr(execution_service, "load_json", lambda file_type, default=None: config)
    monkeypatch.setattr(
        execution_service,
        "get_market_data",
        lambda force_refresh=False: ({}, {"FAS": 134.0}),
    )
    monkeypatch.setattr(
        execution_service.raoeo,
        "calculate_orders",
        lambda **kwargs: (
            [],
            {
                "ticker_info": {},
                "skipped_buy_budgets": {"FAS": 83.33},
            },
        ),
    )
    monkeypatch.setattr(
        execution_service,
        "save_json",
        lambda file_type, data: saved.setdefault("history", data),
    )

    report = execution_service.run_raoeo_strategy(execute=True)

    assert report["status"].value == "skipped"
    assert saved["history"][0]["raoeo"]["orders"] == []
    assert saved["history"][0]["raoeo"]["skipped_buy_budgets"] == {"FAS": 83.33}


def test_run_va_with_all_targets_disabled_stops_before_history(monkeypatch):
    config = {
        "value_averaging": {
            "enabled": True,
            "targets": {
                "QLD": {"enabled": False},
                "TQQQ": {"enabled": False},
            },
        },
    }
    monkeypatch.setattr(
        execution_service,
        "_get_market_status",
        lambda today: {"is_market_open": True, "is_holiday": False, "message": ""},
    )
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: config,
    )
    monkeypatch.setattr(
        execution_service,
        "_load_history",
        lambda: (_ for _ in ()).throw(
            AssertionError("disabled VA must not check history")
        ),
    )
    monkeypatch.setattr(
        execution_service,
        "get_market_data",
        lambda force_refresh=False: (_ for _ in ()).throw(
            AssertionError("disabled VA must not fetch market data")
        ),
    )

    report = execution_service.run_va_strategy(execute=False)

    assert report["status"].value == "disabled"


def test_run_va_reuses_empty_order_history_without_fetching_data(monkeypatch):
    class FrozenDateTime:
        @classmethod
        def now(cls, tz=None):
            return tz.localize(dt.datetime(2026, 6, 17, 8, 12, 4))

    config = {
        "value_averaging": {
            "enabled": True,
            "targets": {
                "QLD": {"enabled": True},
            },
        },
    }
    history = [{
        "date": "2026-06-17",
        "va": {
            "time": "08:12:04",
            "status": "skipped",
            "orders": [],
            "targets_context": {"QLD": {"day_count": 3}},
            },
        }]
    monkeypatch.setattr(execution_service, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        execution_service,
        "_get_market_status",
        lambda today: {"is_market_open": True, "is_holiday": False, "message": ""},
    )
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: config,
    )
    monkeypatch.setattr(execution_service, "_load_history", lambda: history)
    monkeypatch.setattr(
        execution_service,
        "get_market_data",
        lambda force_refresh=False: (_ for _ in ()).throw(
            AssertionError("VA history reuse must not fetch market data")
        ),
    )

    report = execution_service.run_va_strategy(execute=False)

    assert report["status"].value == "skipped"
    assert report["orders"] == []
    assert report["pending_orders"] == []
    assert report["info"]["targets_context"] == {"QLD": {"day_count": 3}}


import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from strategy import execution_service, rebalancing
from strategy.base import OrderSide


def test_rebalancing_uses_orderable_usd_instead_of_portfolio_cash():
    config = {
        "seed": 2000,
        "assets": [
            {"ticker": "TQQQ", "target_weight": 0.5},
            {"ticker": "SCHD", "target_weight": 0.5},
        ],
        "rebalance_threshold": 0.05,
    }
    portfolio = {
        "TQQQ": {"qty": 10, "cur_price": 100.0, "avg_price": 100.0},
        "SCHD": {"qty": 0, "cur_price": 100.0, "avg_price": 0.0},
        "USD cash": {"qty": 0.0},
    }

    orders, info = rebalancing.calculate_orders(
        config=config,
        portfolio=portfolio,
        current_prices={"TQQQ": 100.0, "SCHD": 100.0},
        orderable_usd=1000.0,
    )

    assert any(order.symbol == "SCHD" for order in orders)
    assert info["orderable_usd"] == 1000.0


def test_run_raoeo_does_not_automatically_query_or_sell_cash_ticker(monkeypatch):
    config = {
        "cash_ticker": "BIL",
        "raoeo": {
            "enabled": True,
            "targets": {
                "TQQQ": {
                    "enabled": True,
                    "seed": 1000,
                    "duration": 1,
                    "phase": [{
                        "name": "initial",
                        "threshold": 1.0,
                        "buy": [{"type": "normal", "ratio": 1.0}],
                        "sell": [],
                    }],
                },
            },
        },
    }
    monkeypatch.setattr(
        execution_service,
        "_get_market_status",
        lambda today: {"is_market_open": True, "is_holiday": False, "message": ""},
    )
    monkeypatch.setattr(execution_service, "_load_history", lambda: [])
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: config,
    )
    monkeypatch.setattr(
        execution_service,
        "get_market_data",
        lambda force_refresh=False: (
            {"BIL": {"qty": 100, "cur_price": 100.0}},
            {"TQQQ": 100.0, "BIL": 100.0},
        ),
    )
    monkeypatch.setattr(
        execution_service,
        "get_orderable_usd",
        lambda symbol, price: (_ for _ in ()).throw(
            AssertionError("automatic RAOEO execution must not fund cash")
        ),
    )

    report = execution_service.run_raoeo_strategy(execute=False)

    assert not any(
        order.symbol == "BIL" and order.side == OrderSide.SELL
        for order in report["orders"]
    )


def test_run_rebalancing_passes_api_orderable_usd_to_calculation(monkeypatch):
    config = {
        "raoeo": {"targets": {}},
        "rebalancing": {
            "enabled": True,
            "seed": 1000,
            "assets": [{"ticker": "TQQQ", "target_weight": 1.0}],
        },
    }
    received = {}
    monkeypatch.setattr(
        execution_service,
        "_get_market_status",
        lambda today: {"is_market_open": True, "is_holiday": False, "message": ""},
    )
    monkeypatch.setattr(execution_service, "_load_history", lambda: [])
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: config,
    )
    monkeypatch.setattr(
        execution_service,
        "get_market_data",
        lambda force_refresh=False: ({}, {"TQQQ": 100.0}),
    )
    monkeypatch.setattr(
        execution_service,
        "get_orderable_usd",
        lambda symbol, price: 3023.49,
    )

    def fake_calculate_orders(**kwargs):
        received.update(kwargs)
        return [], {}

    monkeypatch.setattr(
        execution_service.rebalancing,
        "calculate_orders",
        fake_calculate_orders,
    )

    execution_service.run_rebalancing_strategy(execute=False)

    assert received["orderable_usd"] == 3023.49


def test_run_va_strategy_can_reuse_market_snapshot(monkeypatch):
    config = {
        "value_averaging": {
            "enabled": True,
            "targets": {"AAPL": {"enabled": True}},
        },
    }
    received = {}
    monkeypatch.setattr(
        execution_service,
        "_get_market_status",
        lambda today: {"is_market_open": True, "is_holiday": False, "message": ""},
    )
    monkeypatch.setattr(execution_service, "_load_history", lambda: [])
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: config,
    )
    monkeypatch.setattr(
        execution_service,
        "get_market_data",
        lambda force_refresh=False: (_ for _ in ()).throw(
            AssertionError("provided market snapshot should be reused")
        ),
    )

    def fake_calculate_orders(**kwargs):
        received.update(kwargs)
        return [], {"AAPL": {"day_count": 1}}

    monkeypatch.setattr(
        execution_service.value_averaging,
        "calculate_orders",
        fake_calculate_orders,
    )
    monkeypatch.setattr(
        execution_service,
        "_save_strategy_to_history",
        lambda *args, **kwargs: None,
    )

    execution_service.run_va_strategy(
        execute=False,
        market_snapshot=({"AAPL": {"qty": 2}}, {"AAPL": 160.0}),
    )

    assert received["portfolio"] == {"AAPL": {"qty": 2}}
    assert received["current_prices"] == {"AAPL": 160.0}


def test_run_strategy_suite_reuses_context_for_raoeo_and_va(monkeypatch):
    config = {
        "raoeo": {
            "enabled": True,
            "targets": {
                "AAPL": {
                    "enabled": True,
                    "seed": 1200,
                    "duration": 12,
                    "phase": [{
                        "name": "initial",
                        "threshold": 1.0,
                        "buy": [],
                        "sell": [],
                    }],
                },
            },
        },
        "value_averaging": {
            "enabled": True,
            "targets": {"MSFT": {"enabled": True}},
        },
    }
    portfolio_calls = []
    va_received = {}
    monkeypatch.setattr(
        execution_service,
        "_get_market_status",
        lambda today: {"is_market_open": True, "is_holiday": False, "message": ""},
    )
    monkeypatch.setattr(execution_service, "_load_history", lambda: [])
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: config,
    )
    monkeypatch.setattr(
        "data.data_service.get_portfolio_data",
        lambda force_refresh=False, scope="all": portfolio_calls.append(
            (force_refresh, scope)
        ) or {
            "merged_data": {
                "AAPL": {"qty": 0, "cur_price": 160.0, "avg_price": 0.0},
                "MSFT": {"qty": 0, "cur_price": 420.0, "avg_price": 0.0},
            },
        },
    )

    def fake_va_calculate_orders(**kwargs):
        va_received.update(kwargs)
        return [], {"MSFT": {"day_count": 1}}

    monkeypatch.setattr(
        execution_service.value_averaging,
        "calculate_orders",
        fake_va_calculate_orders,
    )
    monkeypatch.setattr(
        execution_service,
        "_save_strategy_to_history",
        lambda *args, **kwargs: None,
    )

    raoeo_report, va_report = execution_service.run_strategy_suite(execute=False)

    assert raoeo_report["info"]["holdings"] is va_received["portfolio"]
    assert raoeo_report["info"]["current_prices"] is va_received["current_prices"]
    assert va_report["status"] == StrategyStatus.SKIPPED
    assert portfolio_calls == [(True, "toss")]
