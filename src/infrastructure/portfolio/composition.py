"""Concrete assembly of the portfolio application use case."""

from dataclasses import dataclass
from typing import Any, Callable

from application.portfolio_service import PortfolioService
from application.ports import PortfolioSource


@dataclass(frozen=True)
class PortfolioServiceDependencies:
    """Concrete collaborators supplied by the composition root."""

    is_kis_ready: Callable[[], bool]
    portfolio_source: PortfolioSource
    save_portfolio: Callable[[dict[str, Any]], None]
    load_weights: Callable[[], dict[str, Any]]
    calculate_targets: Callable[..., tuple[dict[str, float], Any, Any]]
    fear_and_greed: Callable[[], Any]
    publish_alert: Callable[[str, str], None]


def build_portfolio_service(
    dependencies: PortfolioServiceDependencies,
) -> PortfolioService:
    """Build the portfolio use case from explicitly supplied adapters."""
    return PortfolioService(
        is_kis_ready=dependencies.is_kis_ready,
        portfolio_source=dependencies.portfolio_source,
        save_portfolio=dependencies.save_portfolio,
        load_weights=dependencies.load_weights,
        calculate_targets=dependencies.calculate_targets,
        fear_and_greed=dependencies.fear_and_greed,
        publish_alert=dependencies.publish_alert,
    )
