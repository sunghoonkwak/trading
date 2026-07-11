import math
import sys
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from strategy.base import OrderSide, StrategyOrder
from strategy.raoeo import calculate_cash_funding_order
from strategy.rebalancing import _build_rebalance_orders


@given(
    buy_price_cents=st.integers(min_value=1, max_value=100_000),
    buy_quantity=st.integers(min_value=1, max_value=10_000),
    orderable_cents=st.integers(min_value=0, max_value=10_000_000),
    cash_holding=st.integers(min_value=0, max_value=100_000),
)
def test_cash_funding_sale_never_exceeds_holding(
    buy_price_cents,
    buy_quantity,
    orderable_cents,
    cash_holding,
):
    buy_price = buy_price_cents / 100
    orderable_usd = orderable_cents / 100
    buy_order = StrategyOrder(
        symbol="TQQQ",
        side=OrderSide.BUY,
        quantity=buy_quantity,
        price=buy_price,
    )

    cash_sale, info = calculate_cash_funding_order(
        orders=[buy_order],
        portfolio={"SGOV": {"qty": cash_holding, "cur_price": 100.0}},
        current_prices={"SGOV": 100.0},
        cash_ticker="SGOV",
        orderable_usd=orderable_usd,
    )

    expected_shortfall = round(
        max(0.0, buy_price * buy_quantity - orderable_usd),
        2,
    )
    assert info["shortfall"] == expected_shortfall
    assert info["required"] is (expected_shortfall > 0)
    if expected_shortfall == 0:
        assert cash_sale is None
    else:
        required_quantity = math.ceil(expected_shortfall / 99.0)
        if cash_holding >= required_quantity:
            assert cash_sale is not None
            assert cash_sale.side == OrderSide.SELL
            assert cash_sale.quantity == required_quantity
            assert 0 < cash_sale.quantity <= cash_holding
        else:
            assert cash_sale is None
            assert "Insufficient" in info["error"]


@st.composite
def valid_rebalance_inputs(draw):
    asset_count = draw(st.integers(min_value=1, max_value=5))
    weights = draw(
        st.lists(
            st.integers(min_value=1, max_value=100),
            min_size=asset_count,
            max_size=asset_count,
        )
    )
    weight_total = sum(weights)
    prices = draw(
        st.lists(
            st.integers(min_value=1, max_value=100_000),
            min_size=asset_count,
            max_size=asset_count,
        )
    )
    quantities = draw(
        st.lists(
            st.integers(min_value=0, max_value=10_000),
            min_size=asset_count,
            max_size=asset_count,
        )
    )
    target_base = draw(st.integers(min_value=1, max_value=10_000_000)) / 100

    asset_data = {
        f"ASSET{index}": {
            "target_weight": weights[index] / weight_total,
            "current_value": quantities[index] * (prices[index] / 100),
            "qty": quantities[index],
            "cur_price": prices[index] / 100,
        }
        for index in range(asset_count)
    }
    return asset_data, target_base


@given(rebalance_input=valid_rebalance_inputs())
def test_rebalance_orders_have_positive_quantities(rebalance_input):
    asset_data, target_base = rebalance_input

    orders, total_buy_required = _build_rebalance_orders(
        asset_data,
        target_base,
    )

    assert all(order.quantity > 0 for order in orders)
    expected_buy_required = sum(
        order.quantity * order.price for order in orders if order.side == OrderSide.BUY
    )
    assert total_buy_required == pytest.approx(expected_buy_required)

    for order in orders:
        source = asset_data[order.symbol]
        if order.side == OrderSide.SELL:
            assert order.quantity <= source["qty"]
        else:
            assert order.quantity * order.price > 0
