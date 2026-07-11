"""Shared, dependency-free conventions for application port contracts."""

from dataclasses import dataclass
from typing import Any, Generic, NewType, Protocol, TypeVar

CorrelationId = NewType("CorrelationId", str)
T = TypeVar("T")


class PortfolioSource(Protocol):
    """Read normalized portfolio data from infrastructure adapters."""

    def fetch(self, *, scope: str) -> dict[str, Any]:
        """Return the established raw portfolio shape for a scope."""


class PortfolioReader(Protocol):
    """Application use case consumed by transport adapters."""

    def get_portfolio_data(
        self,
        force_refresh: bool = False,
        scope: str = "all",
    ) -> dict[str, Any]:
        """Return the established processed portfolio result."""


class StrategyOrderExecutor(Protocol):
    """Execute one domain order through the configured broker adapter."""

    def execute(self, order: Any) -> tuple[bool, str]:
        """Return the established accepted/rejected order result."""


class MarketPriceReader(Protocol):
    """Read current prices for transport adapters without a broker import."""

    def get_current_price(self, ticker: str) -> float:
        """Return a cached or current market price."""

    def fetch_price(self, ticker: str) -> float:
        """Fetch a current market price when no cached value exists."""


class OpenOrderReader(Protocol):
    """Read the established open-order report for a transport adapter."""

    def fetch_open_orders(self) -> tuple[Any, int, int, int | None]:
        """Return open orders and the established broker count breakdown."""


@dataclass(frozen=True)
class OperationResult(Generic[T]):
    """A redaction-safe result returned by a port without raising secrets."""

    value: T | None = None
    error: str | None = None
    correlation_id: CorrelationId | None = None
    ambiguous: bool = False

    @property
    def success(self) -> bool:
        return self.error is None and not self.ambiguous


_SENSITIVE_KEYS = {
    "account", "account_no", "account_number", "authorization", "token",
    "secret", "appkey", "app_key", "appsecret", "app_secret",
}


def redact_value(value: Any) -> Any:
    """Recursively mask values whose mapping key denotes a credential or account."""
    if isinstance(value, dict):
        return {
            key: "***" if str(key).lower() in _SENSITIVE_KEYS else redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    return value
