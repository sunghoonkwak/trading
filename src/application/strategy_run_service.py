"""Application use cases for running configured trading strategies."""

from collections.abc import Callable
from typing import Any


class StrategyRunService:
    """Expose strategy runs without binding callers to broker infrastructure."""

    def __init__(
        self,
        *,
        run_raoeo: Callable[..., dict[str, Any]],
        run_value_averaging: Callable[..., dict[str, Any]],
        run_rebalancing: Callable[..., dict[str, Any]],
    ) -> None:
        self._run_raoeo = run_raoeo
        self._run_value_averaging = run_value_averaging
        self._run_rebalancing = run_rebalancing

    def run_raoeo(self, *, execute: bool = False) -> dict[str, Any]:
        """Run the configured RAOEO strategy."""
        return self._run_raoeo(execute=execute)

    def run_value_averaging(self, *, execute: bool = False) -> dict[str, Any]:
        """Run the configured value-averaging strategy."""
        return self._run_value_averaging(execute=execute)

    def run_rebalancing(self, *, execute: bool = False) -> dict[str, Any]:
        """Run the configured rebalancing strategy."""
        return self._run_rebalancing(execute=execute)
