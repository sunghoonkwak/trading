import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from strategy import raoeo
from strategy.base import OrderSide


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


def test_cash_funding_sell_uses_full_buy_budget_without_orderable_usd():
    cash_sell, info = _cash_funding()

    assert cash_sell.quantity == 10
    assert cash_sell.price == 99.0
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


def test_rejects_non_positive_duration():
    targets_config = _targets_config()
    targets_config["TQQQ"]["duration"] = 0

    try:
        raoeo.calculate_orders(
            targets_config=targets_config,
            portfolio=_portfolio(),
            current_prices={"TQQQ": 100.0, "BIL": 100.0},
        )
    except ValueError as exc:
        assert "duration" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-positive duration")


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


def test_unbuyable_budget_is_reported_as_ticker_total():
    targets_config = _target_config(
        "FAS",
        seed=0.01,
        duration=1,
        buy_rules=[{"type": "normal", "ratio": 1.0}],
    )

    orders, info = raoeo.calculate_orders(
        targets_config=targets_config,
        portfolio={"FAS": {"qty": 0, "avg_price": 0.0, "cur_price": 140.0}},
        current_prices={"FAS": 140.0},
    )

    assert orders == []
    assert info["skipped_buy_budgets"] == {"FAS": 0.01}


def test_defensive_phase_buys_average_with_full_budget_when_normal_gets_zero():
    targets_config = _target_config(
        "FAS",
        seed=166,
        duration=1,
        buy_rules=[
            {"type": "average", "ratio": 0.5, "price_percent_cap": 0.0},
            {"type": "normal", "ratio": 0.5, "price_percent_cap": 0.06},
        ],
    )

    orders, info = raoeo.calculate_orders(
        targets_config=targets_config,
        portfolio=_fas_holding(),
        current_prices={"FAS": 134.0},
    )

    buy_orders = _buy_orders(orders)

    assert [(order.reason, order.quantity, order.price) for order in buy_orders] == [
        ("Buy Average", 1, 133.98),
    ]
    assert buy_orders[0].target_budget == 166.0
    assert info["ticker_info"]["FAS"]["skipped_buy_budget"] == 0.0
