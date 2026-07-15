"""History recovery policy shared by strategy execution flows."""
import logging
from typing import Dict, List, Tuple

from domain.strategy.base import OrderSide, StrategyOrder, StrategyStatus
from domain.strategy.constants import ORDER_TYPE_LIMIT


def restore_history_orders(
    report: Dict, strategy_history: Dict
) -> Tuple[List[StrategyOrder], List[StrategyOrder]]:
    """Restore history orders and classify them for a strategy report."""
    restored = _restore_orders(strategy_history)
    all_orders = [order for order, _ in restored]
    succeeded = [order for order, success in restored if success]
    failed = [order for order, success in restored if not success]
    report["orders"] = all_orders
    report["succeeded_orders"] = succeeded
    report["pending_orders"] = failed
    return succeeded, failed


def has_ambiguous_order(strategy_history: Dict) -> bool:
    """Return whether automatic retry must wait for operator reconciliation."""
    return any(order.get("ambiguous", False) for order in strategy_history.get("orders", []))


def mark_ambiguous_order_error(report: Dict) -> None:
    """Expose an ambiguous broker outcome as a non-retryable report error."""
    report["status"] = StrategyStatus.ERROR
    report["error"] = "Ambiguous order outcome requires reconciliation."
    report["pending_orders"] = []


def _restore_orders(strategy_history: Dict) -> List[Tuple[StrategyOrder, bool]]:
    restored = []
    for order_data in strategy_history.get("orders", []):
        try:
            order = StrategyOrder(
                symbol=order_data["ticker"],
                side=OrderSide[order_data["side"]],
                quantity=order_data["qty"],
                price=order_data["price"],
                order_type=order_data.get("order_type", ORDER_TYPE_LIMIT),
                reason=order_data.get("reason", ""),
                target_budget=order_data.get("target_budget"),
                correlation_id=order_data.get("correlation_id"),
            )
            restored.append((order, order_data.get("success", False)))
        except Exception as error:
            logging.error("Failed to restore order: %s, error: %s", order_data, error)
    return restored
