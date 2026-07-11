"""Concrete composition of the portfolio application use case."""

from application.portfolio_service import PortfolioService
from core.display import add_alert
from data.config_manager import ConfigFile, load_json, save_json
from infrastructure.portfolio.integration import IntegratedPortfolioSource
from state.system_state import is_kis_ready
from utils.market_utils import get_fear_and_greed


def build_portfolio_service() -> PortfolioService:
    """Compose the portfolio use case from the current infrastructure adapters."""
    from data.calculate_weights import calculate_target_weights

    return PortfolioService(
        is_kis_ready=is_kis_ready,
        portfolio_source=IntegratedPortfolioSource(),
        save_portfolio=lambda value: save_json(ConfigFile.PORTFOLIO, value),
        load_weights=lambda: load_json(ConfigFile.PORTFOLIO_WEIGHTS),
        calculate_targets=calculate_target_weights,
        fear_and_greed=get_fear_and_greed,
        publish_alert=add_alert,
    )
