"""Application service for selecting strategy account operations."""

from typing import Any, Callable, Dict, Tuple

from domain.strategy.base import StrategyOrder

KIS_BROKER = "kis"
TOSS_BROKER = "toss"
_ACCOUNT_NAMES = {
    KIS_BROKER: "한국투자증권",
    TOSS_BROKER: "토스",
}


class StrategyBrokerService:
    """Select injected broker operations from the configured strategy account."""

    def __init__(
        self,
        load_strategy_config: Callable[[], Dict[str, Any]],
        kis_orderable_usd: Callable[[str, float], float] | None = None,
        toss_orderable_usd: Callable[[str, float], float] | None = None,
        kis_place_order: Callable[[StrategyOrder], Tuple[bool, str]] | None = None,
        toss_place_order: Callable[[StrategyOrder], Tuple[bool, str]] | None = None,
    ):
        self._load_strategy_config = load_strategy_config
        self._kis_orderable_usd = kis_orderable_usd
        self._toss_orderable_usd = toss_orderable_usd
        self._kis_place_order = kis_place_order
        self._toss_place_order = toss_place_order

    def get_strategy_broker_name(self) -> str:
        """Return the configured strategy broker name."""
        config = self._load_strategy_config()
        broker_name = str(config.get("strategy_broker", KIS_BROKER)).strip().lower()
        if broker_name not in _ACCOUNT_NAMES:
            raise ValueError(
                "strategy_broker must be one of: "
                f"{', '.join(sorted(_ACCOUNT_NAMES))}"
            )
        return broker_name

    def get_strategy_account_name(self) -> str:
        """Return the portfolio account name for the configured strategy broker."""
        return _ACCOUNT_NAMES[self.get_strategy_broker_name()]

    def get_orderable_usd(self, symbol: str, order_price: float) -> float:
        """Return USD buying power for the configured strategy broker."""
        operation = self._select_operation(
            self._kis_orderable_usd,
            self._toss_orderable_usd,
        )
        return operation(symbol, order_price)

    def place_order(self, order: StrategyOrder) -> Tuple[bool, str]:
        """Place a strategy order through the configured strategy broker."""
        operation = self._select_operation(
            self._kis_place_order,
            self._toss_place_order,
        )
        return operation(order)

    def _select_operation(self, kis_operation, toss_operation):
        operation = (
            toss_operation
            if self.get_strategy_broker_name() == TOSS_BROKER
            else kis_operation
        )
        if operation is None:
            raise RuntimeError("Strategy broker operations are not configured.")
        return operation
