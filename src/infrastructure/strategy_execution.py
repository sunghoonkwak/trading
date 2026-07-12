"""Infrastructure assembly for the application strategy execution service."""

from application.strategy_execution import (
    StrategyExecutionDependencies,
    configure_strategy_execution,
)
from broker import market_data, strategy_broker
from data.config_manager import ConfigFile, load_json, save_json
from infrastructure.portfolio import build_portfolio_service


def configure_strategy_execution_service() -> None:
    """Inject file, portfolio, market-data, and broker adapters once at startup."""
    configure_strategy_execution(
        StrategyExecutionDependencies(
            load_strategy_config=lambda: load_json(ConfigFile.STRATEGY_CONFIG, default={}),
            load_history=lambda: load_json(ConfigFile.STRATEGY_HISTORY, default=[]),
            save_history=lambda history: save_json(ConfigFile.STRATEGY_HISTORY, history),
            fetch_prices=market_data.fetch_prices,
            strategy_broker_name=strategy_broker.get_strategy_broker_name,
            get_orderable_usd=strategy_broker.get_orderable_usd,
            execute_order=strategy_broker.place_order,
            portfolio_reader_factory=build_portfolio_service,
        )
    )
