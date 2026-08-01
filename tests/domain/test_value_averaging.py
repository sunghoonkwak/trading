import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from domain.strategy import value_averaging
from domain.strategy.base import OrderSide
from domain.strategy.constants import ORDER_TYPE_LIMIT, ORDER_TYPE_LOC


def test_empty_and_disabled_targets_produce_no_orders(caplog):
    assert value_averaging.calculate_orders({}, {}, {}, [], "2026-07-09") == (
        [],
        {},
    )

    orders, contexts = value_averaging.calculate_orders(
        {"SOXL": {"enabled": False, "daily_budget": 100}},
        {},
        {},
        [],
        "2026-07-09",
    )

    assert orders == []
    assert contexts == {}
    assert "No targets configured" in caplog.text


def test_new_ticker_builds_loc_buy_order_and_context():
    orders, contexts = value_averaging.calculate_orders(
        {
            "SOXL": {
                "daily_budget": 1_000,
                "target": 10_000,
                "threshold_rate": 0.1,
            }
        },
        {"SOXL": {"current_value_usd": 200, "avg_price": 8}},
        {"SOXL": 10},
        [],
        "2026-07-09",
    )

    assert len(orders) == 1
    order = orders[0]
    assert order.symbol == "SOXL"
    assert order.side is OrderSide.BUY
    assert order.quantity == 80
    assert order.price == 10.5
    assert order.order_type == ORDER_TYPE_LOC
    assert contexts["SOXL"] == {
        "day_count": 1,
        "daily_budget": 1_000,
        "target_value": 1_000,
        "current_value": 200,
        "daily_target_amount": 800,
        "divergence_rate": 0.8,
        "threshold_rate": 0.1,
        "already_executed": False,
        "cur_price": 10,
        "avg_price": 8,
    }


def test_krw_holding_builds_market_sell_order():
    orders, contexts = value_averaging.calculate_orders(
        {"005930": {"daily_budget": 100_000, "threshold_rate": 0.01}},
        {
            "005930": {
                "currency": "KRW",
                "current_value_krw": 250_000,
                "cur_price": 50_000,
            }
        },
        {},
        [],
        "2026-07-09",
    )

    assert len(orders) == 1
    assert orders[0].side is OrderSide.SELL
    assert orders[0].quantity == 3
    assert orders[0].price == 0
    assert orders[0].order_type == ORDER_TYPE_LIMIT
    assert contexts["005930"]["daily_target_amount"] == -150_000


@pytest.mark.parametrize(
    ("target_amount", "price"),
    [(5, 10), (-5, 10), (0, 10)],
)
def test_sub_share_or_zero_difference_does_not_create_order(
    target_amount,
    price,
):
    assert value_averaging._build_order(
        "SOXL",
        1,
        price,
        target_amount,
    ) is None


def test_saved_va_history_increments_day_and_applies_target_cap():
    history = [
        {
            "date": "2026-07-08",
            "va": {
                "targets_context": {
                    "SOXL": {
                        "day_count": 4,
                        "results": [],
                    }
                }
            },
        }
    ]

    orders, contexts = value_averaging.calculate_orders(
        {"SOXL": {"daily_budget": 1_000, "target": 3_000}},
        {"SOXL": {"current_value_usd": 3_000}},
        {"SOXL": 10},
        history,
        "2026-07-09",
    )

    assert orders == []
    assert contexts["SOXL"]["day_count"] == 5
    assert contexts["SOXL"]["target_value"] == 3_000
    assert contexts["SOXL"]["divergence_rate"] == 0


@pytest.mark.parametrize(
    "result",
    [
        {"success": True, "type": "buy"},
        {"executed": True, "type": "sell"},
    ],
)
def test_successful_order_today_prevents_duplicate(result):
    history = [
        {
            "date": "2026-07-09",
            "va": {
                "targets_context": {
                    "SOXL": {
                        "day_count": 3,
                        "results": [result],
                    }
                }
            },
        }
    ]

    orders, contexts = value_averaging.calculate_orders(
        {"SOXL": {"daily_budget": 1_000}},
        {},
        {"SOXL": 10},
        history,
        "2026-07-09",
    )

    assert orders == []
    assert contexts["SOXL"]["day_count"] == 3
    assert contexts["SOXL"]["already_executed"] is True


def test_skip_result_today_allows_order():
    history = [
        {
            "date": "2026-07-09",
            "va": {
                "targets_context": {
                    "SOXL": {
                        "day_count": 2,
                        "results": [{"success": True, "type": "skip"}],
                    }
                }
            },
        }
    ]

    orders, contexts = value_averaging.calculate_orders(
        {"SOXL": {"daily_budget": 100}},
        {},
        {"SOXL": 10},
        history,
        "2026-07-09",
    )

    assert len(orders) == 1
    assert contexts["SOXL"]["day_count"] == 2
    assert contexts["SOXL"]["already_executed"] is False


def test_threshold_and_missing_price_suppress_orders_but_keep_context():
    orders, contexts = value_averaging.calculate_orders(
        {
            "LOW": {"daily_budget": 100, "threshold_rate": 0.2},
            "NOPRICE": {"daily_budget": 100},
        },
        {"LOW": {"current_value_usd": 90}},
        {"LOW": 10},
        [],
        "2026-07-09",
    )

    assert orders == []
    assert contexts["LOW"]["divergence_rate"] == 0.1
    assert contexts["NOPRICE"]["cur_price"] == 0


@pytest.mark.parametrize("current_price", [0.0, -10.0])
def test_non_positive_price_never_creates_value_averaging_order(current_price):
    orders, contexts = value_averaging.calculate_orders(
        {"SOXL": {"daily_budget": 100, "threshold_rate": 0}},
        {"SOXL": {"current_value_usd": -20}},
        {"SOXL": current_price},
        [],
        "2026-07-09",
    )

    assert orders == []
    assert contexts["SOXL"]["cur_price"] == max(current_price, 0)
    assert contexts["SOXL"]["daily_target_amount"] == 120


@pytest.mark.parametrize(
    ("target", "accumulated", "expected"),
    [(10, 0, 1.0), (0, 0, 0.0), (-10, 0, 0.0)],
)
def test_divergence_without_accumulated_target(target, accumulated, expected):
    assert value_averaging._divergence_rate(target, accumulated) == expected
