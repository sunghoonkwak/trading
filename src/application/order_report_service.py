"""Application use cases for order execution and structured result data."""

from collections.abc import Callable
from typing import Any

from domain.strategy.base import StrategyOrder


class OrderReportService:
    """Execute one domain order through an injected order port."""

    def __init__(self, *, execute_order: Callable[[StrategyOrder], tuple[bool, str]]) -> None:
        self._execute_order = execute_order

    def execute(self, order: StrategyOrder) -> dict[str, Any]:
        """Return channel-neutral execution result data."""
        success, message = self._execute_order(order)
        return {"order": order, "success": success, "message": message}
