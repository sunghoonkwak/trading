"""Application use cases for order execution and structured result data."""

from collections.abc import Callable
from typing import Any

from domain.strategy.base import OrderSide, StrategyOrder


class OrderReportService:
    """Execute one domain order through an injected order port."""

    def __init__(
        self,
        *,
        execute_order: Callable[[StrategyOrder], tuple[bool, str]],
        sleep: Callable[[int], None] | None = None,
    ) -> None:
        self._execute_order = execute_order
        self._sleep = sleep

    def execute(self, order: StrategyOrder) -> dict[str, Any]:
        """Return channel-neutral execution result data."""
        success, message = self._execute_order(order)
        return {"order": order, "success": success, "message": message}

    def execute_many(
        self,
        orders: list[StrategyOrder],
        *,
        sell_first: bool = False,
        sell_wait_seconds: int = 0,
    ) -> list[dict[str, Any]]:
        """Execute domain orders in the established funding-safe order."""
        if not sell_first:
            return [self.execute(order) for order in orders]

        sells = [order for order in orders if order.side == OrderSide.SELL]
        buys = [order for order in orders if order.side == OrderSide.BUY]
        results = [self.execute(order) for order in sells]
        if sells and buys and sell_wait_seconds > 0:
            if self._sleep is None:
                raise RuntimeError("A sleep port is required for sell-first execution.")
            self._sleep(sell_wait_seconds)
        results.extend(self.execute(order) for order in buys)
        return results
