import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from domain.strategy.base import OrderSide
from domain.strategy.raoeo import calculate_orders


def _target_config(**overrides):
    return {
        "seed": 2_000,
        "duration": 10,
        "phase": [
            {
                "name": "initial",
                "threshold": 1.0,
                "buy": [{"type": "normal", "ratio": 1.0}],
                "sell": [{"type": "Limit", "ratio": 1.0, "profit": 0.1}],
            }
        ],
        **overrides,
    }


def test_target_buy_enabled_false_skips_buys_in_every_phase():
    orders, _ = calculate_orders(
        targets_config={"SOXL": _target_config(enabled={"buy": False, "sell": True})},
        portfolio={"SOXL": {"qty": 2, "avg_price": 100.0}},
        current_prices={"SOXL": 100.0},
    )

    assert [order.side for order in orders] == [OrderSide.SELL]


def test_target_sell_enabled_false_skips_sells_in_every_phase():
    orders, _ = calculate_orders(
        targets_config={"SOXL": _target_config(enabled={"buy": True, "sell": False})},
        portfolio={"SOXL": {"qty": 2, "avg_price": 100.0}},
        current_prices={"SOXL": 100.0},
    )

    assert [order.side for order in orders] == [OrderSide.BUY]
