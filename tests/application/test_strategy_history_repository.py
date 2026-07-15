from application.strategy_history_repository import (
    build_cash_funding_history_entry,
    build_merged_history_entries,
    build_strategy_history_data,
    save_strategy,
)
from domain.strategy.base import OrderSide, StrategyOrder, StrategyStatus


def _order(correlation_id: str | None = None) -> StrategyOrder:
    return StrategyOrder(
        "TQQQ",
        OrderSide.BUY,
        2,
        100.0,
        reason="rebalance",
        target_budget=200.0,
        correlation_id=correlation_id,
    )


def test_build_strategy_history_data_preserves_execution_metadata():
    order = _order("run-1")

    result = build_strategy_history_data(
        {
            "status": StrategyStatus.PARTIAL,
            "execution_results": [
                {
                    "order": order,
                    "success": False,
                    "message": "broker timeout",
                    "ambiguous": True,
                }
            ],
            "info": {"skipped_buy_budgets": {"TQQQ": 200.0}},
        },
        "raoeo",
        extra_fields={"context": {"source": "test"}},
    )

    assert result["status"] == "partial"
    assert result["context"] == {"source": "test"}
    assert result["skipped_buy_budgets"] == {"TQQQ": 200.0}
    assert result["orders"] == [
        {
            "ticker": "TQQQ",
            "side": "BUY",
            "qty": 2,
            "price": 100.0,
            "order_type": "LIMIT",
            "reason": "rebalance",
            "success": False,
            "message": "broker timeout",
            "ambiguous": True,
            "target_budget": 200.0,
            "correlation_id": "run-1",
        }
    ]


def test_build_merged_history_entries_keeps_prior_successes():
    entries = build_merged_history_entries(
        [_order("prior")],
        [{"order": _order("retry"), "success": True, "message": "accepted"}],
    )

    assert [(entry["correlation_id"], entry["success"]) for entry in entries] == [
        ("prior", True),
        ("retry", True),
    ]


def test_build_cash_funding_history_entry_preserves_reconciliation_fields():
    entry = build_cash_funding_history_entry(
        {
            "order": _order("funding-1"),
            "success": False,
            "message": "broker timeout",
            "ambiguous": True,
        }
    )

    assert entry["correlation_id"] == "funding-1"
    assert entry["ambiguous"] is True
    assert entry["message"] == "broker timeout"


def test_save_strategy_delegates_to_history_service():
    calls = []

    class HistoryService:
        def save_strategy(self, date, key, data):
            calls.append((date, key, data))

    save_strategy(HistoryService(), "2026-07-15", "raoeo", {"orders": []})

    assert calls == [("2026-07-15", "raoeo", {"orders": []})]
