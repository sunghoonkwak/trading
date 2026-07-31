"""Shared lifecycle state for configured strategy runs."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from application.order_report_service import OrderReportService
from application.strategy_run_service import StrategyHistoryService


@dataclass
class StrategyExecutionSession:
    """Dependencies and state common to a single strategy execution."""

    today: str
    market_status: Dict[str, Any]
    report: Dict[str, Any]
    history_service: StrategyHistoryService
    order_report_service: OrderReportService


def begin_strategy_execution(
    *,
    today: str,
    get_market_status: Callable[[str], Dict[str, Any]],
    build_report: Callable[[str, Dict[str, Any]], Dict[str, Any]],
    history_service: StrategyHistoryService,
    order_report_service: OrderReportService,
) -> StrategyExecutionSession:
    market_status = get_market_status(today)
    return StrategyExecutionSession(
        today=today,
        market_status=market_status,
        report=build_report(today, market_status),
        history_service=history_service,
        order_report_service=order_report_service,
    )


def active_targets(config: Dict, strategy_key: str) -> Dict:
    """Return enabled target configurations for a strategy section."""
    targets = config.get(strategy_key, {}).get("targets", {})
    return {
        ticker: target
        for ticker, target in targets.items()
        if _target_has_enabled_orders(target)
    }


def _target_has_enabled_orders(target: Dict) -> bool:
    enabled = target.get("enabled", True)
    if isinstance(enabled, dict):
        return enabled.get("buy", True) is True or enabled.get("sell", True) is True
    return enabled is True


def history_for_date(history: List[Dict], today: str) -> Optional[Dict]:
    """Return today's history entry, if it exists."""
    return next((entry for entry in history if entry.get("date") == today), None)
