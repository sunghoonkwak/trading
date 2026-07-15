"""Strategy history record serialization and persistence boundary."""
from datetime import datetime
from typing import Dict, List, Optional

from application.strategy_run_service import StrategyHistoryService
from domain.strategy.base import StrategyOrder, StrategyStatus
from domain.strategy.constants import TZ_ET


def build_order_history_entry(
    order: StrategyOrder,
    success: bool,
    message: str,
    *,
    ambiguous: bool = False,
) -> Dict:
    entry = {
        "ticker": order.symbol,
        "side": order.side.name,
        "qty": order.quantity,
        "price": order.price,
        "order_type": order.order_type,
        "reason": order.reason,
        "success": success,
        "message": message,
        "ambiguous": ambiguous,
    }
    if order.target_budget is not None:
        entry["target_budget"] = order.target_budget
    if order.correlation_id:
        entry["correlation_id"] = order.correlation_id
    return entry


def build_strategy_history_data(
    report: Dict,
    strategy_key: str,
    extra_fields: Optional[Dict] = None,
) -> Dict:
    data = {
        "time": datetime.now(TZ_ET).strftime("%H:%M:%S"),
        "status": report["status"].value
        if isinstance(report["status"], StrategyStatus)
        else report["status"],
        "orders": [],
    }
    if extra_fields:
        data.update(extra_fields)
    if strategy_key == "raoeo":
        skipped = report.get("info", {}).get("skipped_buy_budgets")
        if skipped:
            data["skipped_buy_budgets"] = skipped
    if report.get("execution_results"):
        for result in report["execution_results"]:
            data["orders"].append(
                build_order_history_entry(
                    result["order"], result["success"], result["message"],
                    ambiguous=result.get("ambiguous", False),
                )
            )
    elif report.get("orders"):
        for order in report["orders"]:
            data["orders"].append(
                build_order_history_entry(order, False, "Calculated Only")
            )
    return data


def build_merged_history_entries(
    succeeded: List[StrategyOrder], results: List[Dict]
) -> List[Dict]:
    return [build_order_history_entry(order, True, "Success") for order in succeeded] + [
        build_order_history_entry(
            result["order"], result["success"], result["message"],
            ambiguous=result.get("ambiguous", False),
        )
        for result in results
    ]


def build_cash_funding_history_entry(result: Dict) -> Dict:
    order = result["order"]
    return {
        "ticker": order.symbol,
        "side": order.side.name,
        "qty": order.quantity,
        "price": order.price,
        "order_type": order.order_type,
        "reason": order.reason,
        "success": result["success"],
        "message": result["message"],
        "ambiguous": result.get("ambiguous", False),
        "correlation_id": order.correlation_id,
    }


def save_strategy(
    history_service: StrategyHistoryService,
    today_str: str,
    strategy_key: str,
    strategy_data: Dict,
) -> None:
    history_service.save_strategy(today_str, strategy_key, strategy_data)


def save_cash_funding_result(
    history_service: StrategyHistoryService,
    today_str: str,
    result: Dict,
) -> List[Dict]:
    if not result or result.get("order") is None:
        return []
    return history_service.save_cash_funding_result(
        today_str,
        build_cash_funding_history_entry(result),
    )
