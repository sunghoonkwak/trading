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


def test_cash_funding_fails_without_cash_ticker_holding():
    cash_sell, info = _cash_funding(cash_ticker_qty=0)

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


def test_normal_buy_carries_forward_unused_order_budget():
    targets_config = {
        "SOXL": {
            "seed": 1000,
            "duration": 1,
            "phase": [
                {
                    "name": "initial",
                    "threshold": 1.0,
                    "buy": [{"type": "normal", "ratio": 1.0}],
                    "sell": [{"type": "Limit", "ratio": 0.0, "profit": 0.1}],
                }
            ],
        }
    }
    history_data = [
        {
            "date": "2026-06-01",
            "raoeo": {
                "orders": [
                    {
                        "ticker": "SOXL",
                        "side": "BUY",
                        "qty": 3,
                        "price": 266.63,
                        "reason": "Buy Normal",
                        "success": True,
                        "target_budget": 1000.0,
                    }
                ]
            },
        }
    ]

    orders, info = raoeo.calculate_orders(
        targets_config=targets_config,
        portfolio={"SOXL": {"qty": 1, "avg_price": 242.4, "cur_price": 240.0}},
        current_prices={"SOXL": 240.0},
        history_data=history_data,
        today_date="2026-06-02",
    )

    buy_order = next(order for order in orders if order.side == OrderSide.BUY)
    assert buy_order.quantity == 4
    assert buy_order.target_budget == 1200.11
    assert info["ticker_info"]["SOXL"]["budget_carryover"] == 200.11
