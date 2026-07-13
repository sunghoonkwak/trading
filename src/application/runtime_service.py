"""Application-facing runtime lifecycle contract."""
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class RuntimeCommandResult:
    success: bool
    message: str
    component: Optional[str] = None
    already_in_state: bool = False


@dataclass(frozen=True)
class RuntimeController:
    """Lifecycle operations injected by the production composition root."""

    start: Callable[[], RuntimeCommandResult]
    stop: Callable[[], RuntimeCommandResult]
    is_running: Callable[[], bool]
