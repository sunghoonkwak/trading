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


def _portfolio(usd_cash=0.0, cash_ticker_qty=100):
    portfolio = {
        "BIL": {"qty": cash_ticker_qty, "avg_price": 100.0, "cur_price": 100.0},
    }
    if usd_cash > 0:
        portfolio["USD cash"] = {
            "qty": usd_cash,
            "avg_price": 1.0,
            "cur_price": 1.0,
            "type": "CASH",
        }
    return portfolio


def _calculate(usd_cash=0.0, cash_ticker_qty=100):
    orders, _ = raoeo.calculate_orders(
        targets_config=_targets_config(),
        portfolio=_portfolio(usd_cash=usd_cash, cash_ticker_qty=cash_ticker_qty),
        current_prices={"TQQQ": 100.0, "BIL": 100.0},
        cash_ticker="BIL",
    )
    return orders


def _cash_sell_order(orders):
    return next(
        order
        for order in orders
        if order.symbol == "BIL" and order.side == OrderSide.SELL
    )


def test_cash_ticker_sell_uses_full_buy_budget_when_usd_cash_is_absent():
    orders = _calculate()

    cash_sell = _cash_sell_order(orders)

    assert cash_sell.quantity == 10
    assert cash_sell.price == 99.0


def test_cash_ticker_sell_only_funds_shortfall_after_kis_usd_cash():
    orders = _calculate(usd_cash=500.0)

    cash_sell = _cash_sell_order(orders)

    assert cash_sell.quantity == 5
    assert "$989.91" in cash_sell.reason
    assert "$500.00" in cash_sell.reason
    assert "$489.91" in cash_sell.reason


def test_cash_ticker_sell_is_skipped_when_kis_usd_cash_covers_buys():
    orders = _calculate(usd_cash=1000.0)

    cash_sell_orders = [
        order
        for order in orders
        if order.symbol == "BIL" and order.side == OrderSide.SELL
    ]

    assert cash_sell_orders == []


def test_cash_ticker_sell_is_capped_by_holding_quantity():
    orders = _calculate(cash_ticker_qty=3)

    cash_sell = _cash_sell_order(orders)

    assert cash_sell.quantity == 3


def test_cash_ticker_sell_is_skipped_without_cash_ticker_holding():
    orders = _calculate(cash_ticker_qty=0)

    cash_sell_orders = [
        order
        for order in orders
        if order.symbol == "BIL" and order.side == OrderSide.SELL
    ]

    assert cash_sell_orders == []


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
