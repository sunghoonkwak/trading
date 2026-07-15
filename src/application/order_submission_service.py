"""Durable order submission boundary for strategy execution."""
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from application.order_report_service import OrderReportService
from domain.strategy.base import StrategyOrder


class DurableOrderSubmissionService:
    """Persist an order intent before broker submission and save its outcome."""

    def __init__(self, order_report_service: OrderReportService) -> None:
        self._order_report_service = order_report_service

    def submit(
        self,
        orders: list[StrategyOrder],
        *,
        persist_intent: Callable[[list[StrategyOrder]], None],
        persist_outcome: Callable[[list[dict[str, Any]]], None] | None = None,
        sell_first: bool = False,
        sell_wait_seconds: int = 0,
    ) -> list[dict[str, Any]]:
        """Submit orders only after durable intent persistence succeeds."""
        for order in orders:
            if not order.correlation_id:
                order.correlation_id = str(uuid4())

        persist_intent(orders)
        results = self._order_report_service.execute_many(
            orders,
            sell_first=sell_first,
            sell_wait_seconds=sell_wait_seconds,
        )
        if persist_outcome is not None:
            persist_outcome(results)
        return results
