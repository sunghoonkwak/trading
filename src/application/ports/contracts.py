"""Shared, dependency-free conventions for application port contracts."""

from dataclasses import dataclass
from typing import Any, Generic, NewType, TypeVar

CorrelationId = NewType("CorrelationId", str)
T = TypeVar("T")


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
