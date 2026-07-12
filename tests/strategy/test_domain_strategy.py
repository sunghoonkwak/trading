import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from domain.strategy import OrderSide, StrategyOrder
from domain.strategy.base import StrategyOrder as LegacyStrategyOrder
from domain.strategy.rebalancing import calculate_orders


def test_domain_strategy_order_values_remain_compatible_with_legacy_imports():
    order = StrategyOrder(symbol="SOXL", side=OrderSide.BUY, quantity=1, price=10.0)

    assert LegacyStrategyOrder is StrategyOrder
    assert str(order) == "[SOXL] BUY 1 (10.00) - "


def test_domain_rebalancing_preserves_missing_price_safe_skip():
    orders, info = calculate_orders(
        config={
            "seed": 1_000,
            "assets": [
                {"ticker": "SOXL", "target_weight": 0.5},
                {"ticker": "TLTW", "target_weight": 0.5},
            ],
        },
        portfolio={"SOXL": {"qty": 1, "cur_price": 10.0}, "TLTW": {}},
        current_prices={"SOXL": 10.0, "TLTW": 0.0},
        orderable_usd=1_000.0,
    )

    assert orders == []
    assert set(info["asset_status"]) == {"SOXL"}
