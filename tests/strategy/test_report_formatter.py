import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from interfaces.telegram.report_formatter import (
    format_rebalancing_report,
    format_strategy_report,
)
from strategy.base import OrderSide, StrategyOrder, StrategyStatus
from strategy.constants import ORDER_TYPE_LOC


def _order(
    symbol="SOXL",
    side=OrderSide.BUY,
    quantity=2,
    price=10.0,
    order_type=ORDER_TYPE_LOC,
):
    return StrategyOrder(
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        order_type=order_type,
        reason="test",
    )


def test_strategy_report_formats_orders_funding_and_execution_results():
    buy = _order()
    funding_sale = _order("SGOV", OrderSide.SELL, 3, 100)
    report = format_strategy_report(
        {
            "date": "2026-07-09",
            "status": StrategyStatus.PARTIAL,
            "market_status": {
                "is_market_open": False,
                "message": "After hours",
            },
            "orders": [buy],
            "succeeded_orders": [buy],
            "info": {
                "ticker_info": {
                    "SOXL": {
                        "phase": "Phase1",
                        "progress_pct": 25,
                        "cur_price": 10,
                        "avg_price": 8,
                    }
                }
            },
            "cash_funding": {
                "buy_budget": 500,
                "orderable_usd": 200,
                "shortfall": 300,
                "order": funding_sale,
            },
            "cash_funding_results": [
                {"success": True, "order": funding_sale},
            ],
            "execution_results": [
                {"success": False, "order": buy, "message": "rejected"},
            ],
        },
        {
            "status": StrategyStatus.SKIPPED,
            "info": {"context_map": {}},
            "orders": [],
        },
    )

    assert "Strategy Report - 2026-07-09" in report
    assert "After hours" in report
    assert "Sell SGOV: 3 @ $100.00" in report
    assert "<b>SOXL</b> Phase1 (25.0%)" in report
    assert "(+25.00%)" in report
    assert "🔄 Partial" in report
    assert "❌ SOXL BUY 2 @ 10.0 (rejected)" in report
    assert "1/2 succeeded" in report


def test_strategy_report_formats_funding_error_and_strategy_errors():
    report = format_strategy_report(
        {
            "error": "RAOEO unavailable",
            "cash_funding": {
                "buy_budget": 100,
                "orderable_usd": 0,
                "shortfall": 100,
                "error": "no holding",
            },
        },
        {"error": "VA unavailable"},
    )

    assert "RAOEO unavailable" in report
    assert "VA unavailable" in report


def test_strategy_report_formats_value_averaging_contexts_and_order_types():
    loc_order = _order("SOXL", OrderSide.BUY, 4, 12)
    report = format_strategy_report(
        {"status": "skipped", "orders": []},
        {
            "status": "executed",
            "orders": [loc_order],
            "info": {
                "context_map": {
                    "SOXL": {
                        "day_count": 2,
                        "target_value": 1_000,
                        "current_value": 700,
                        "daily_target_amount": 300,
                        "cur_price": 12,
                        "avg_price": 15,
                    },
                    "SCHD": {
                        "day_count": 3,
                        "target_value": 2_000,
                        "current_value": 2_100,
                        "daily_target_amount": -100,
                        "cur_price": 20,
                        "avg_price": 0,
                    },
                }
            },
        },
    )

    assert "<b>SOXL</b> (Day 2)" in report
    assert "(-20.00%)" in report
    assert "Diff $300" in report
    assert "BUY 4 shares (LOC)" in report
    assert "Diff -$100" in report
    assert "✅ No orders needed." in report


def test_rebalancing_report_handles_error_and_disabled_status():
    assert "bad input" in format_rebalancing_report({"error": "bad input"})
    assert "⚪ Disabled" in format_rebalancing_report(
        {"status": StrategyStatus.DISABLED},
    )


def test_rebalancing_report_formats_assets_orders_and_results():
    order = _order("QQQM", OrderSide.BUY, 5, 200)
    report = format_rebalancing_report(
        {
            "date": "2026-07-09",
            "status": "partial",
            "market_status": {
                "is_market_open": False,
                "message": "Holiday",
            },
            "info": {
                "seed": 10_000,
                "orderable_usd": 1_000,
                "total_available": 1_500,
                "scale_factor": 0.5,
                "asset_status": {
                    "QQQM": {
                        "cur_w": 30,
                        "diff_w": 5,
                        "qty": 10,
                        "cur_val": 2_000,
                        "cur_price": 200,
                        "avg_price": 160,
                    }
                },
            },
            "orders": [order],
            "execution_results": [
                {"success": True, "order": order},
            ],
        }
    )

    assert "Rebalancing Report - 2026-07-09" in report
    assert "Holiday" in report
    assert "Target Seed: $10,000" in report
    assert "Available USD: $1,500.00" in report
    assert "Scaled by 50.0%" in report
    assert "QQQM: 30% (+5%p)" in report
    assert "(+25.00%)" in report
    assert "Proposed Orders" in report
    assert "1/1 succeeded" in report
