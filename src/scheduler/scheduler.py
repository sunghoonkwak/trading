"""Deprecated compatibility exports for the scheduler interface runner."""

from data.data_service import build_portfolio_service
from interfaces.scheduler.runner import (
    set_portfolio_reader,
    stop_scheduler,
)
from interfaces.scheduler.runner import (
    start_scheduler as _start_scheduler,
)

__all__ = ["start_scheduler", "stop_scheduler"]


def start_scheduler() -> None:
    """Start the scheduler with the legacy portfolio-service composition."""
    set_portfolio_reader(build_portfolio_service())
    _start_scheduler()
