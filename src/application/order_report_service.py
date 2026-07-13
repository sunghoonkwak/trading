"""Application use cases for order execution and structured result data."""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from application.ports import StrategyOrderExecutor
from domain.strategy.base import OrderSide, StrategyOrder, StrategyStatus


class OrderManagementService:
    """Application facade for channel-neutral open-order controls."""

    def __init__(
        self,
        *,
        sync_open_orders: Callable[[], bool],
        fetch_open_orders: Callable[[], tuple[Any, int, int, int | None]],
        execute_manage_action: Callable[[str, str, Any, Any], tuple[Any, str | None]],
    ) -> None:
        self._sync_open_orders = sync_open_orders
        self._fetch_open_orders = fetch_open_orders
        self._execute_manage_action = execute_manage_action

    def sync_open_orders(self) -> bool:
        """Synchronize the established cross-broker open-order view."""
        return self._sync_open_orders()

    def fetch_open_orders(self) -> tuple[Any, int, int, int | None]:
        """Return the established cross-broker open-order report data."""
        return self._fetch_open_orders()

    def execute_manage_action(
        self, market: str, action_type: str, order_data: Any, new_price: Any
    ) -> tuple[Any, str | None]:
        """Submit one explicit cancel or correction action."""
        return self._execute_manage_action(market, action_type, order_data, new_price)


class OrderReportService:
    """Execute one domain order through an injected order port."""

    def __init__(
        self,
        *,
        execute_order: Callable[[StrategyOrder], tuple[bool, str]] | StrategyOrderExecutor,
        sleep: Callable[[int], None] | None = None,
        reconcile_order: Callable[[str], bool] | None = None,
    ) -> None:
        self._execute_order = execute_order
        self._sleep = sleep
        self._reconcile_order = reconcile_order

    def execute(self, order: StrategyOrder) -> dict[str, Any]:
        """Return channel-neutral execution result data."""
        if not order.correlation_id:
            order.correlation_id = str(uuid4())
        if callable(self._execute_order):
            success, message = self._execute_order(order)
        else:
            success, message = self._execute_order.execute(order)
        ambiguous = message.startswith("[AMBIGUOUS]")
        reconciled = False
        if ambiguous and self._reconcile_order is not None:
            reconciled = self._reconcile_order(order.correlation_id)
            if reconciled:
                success = True
                ambiguous = False
        return {
            "order": order,
            "success": success,
            "message": message,
            "ambiguous": ambiguous,
            "reconciled": reconciled,
            "correlation_id": order.correlation_id,
        }

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

    def retry_failed(
        self,
        orders: list[StrategyOrder],
        *,
        sell_first: bool = False,
        sell_wait_seconds: int = 0,
    ) -> dict[str, Any]:
        """Retry historical failures and return structured result data."""
        results = self.execute_many(
            orders,
            sell_first=sell_first,
            sell_wait_seconds=sell_wait_seconds,
        )
        succeeded = [result["order"] for result in results if result["success"]]
        pending = [result["order"] for result in results if not result["success"]]
        return {
            "execution_results": results,
            "status": StrategyStatus.EXECUTED if not pending else StrategyStatus.PARTIAL,
            "succeeded_orders": succeeded,
            "pending_orders": pending,
        }
