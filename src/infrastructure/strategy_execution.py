"""Infrastructure assembly for the application strategy execution service."""

from application.strategy_execution import (
    StrategyExecutionDependencies,
    configure_strategy_execution,
)


def configure_strategy_execution_service(
    dependencies: StrategyExecutionDependencies,
) -> None:
    """Register strategy execution collaborators chosen by the composition root."""
    configure_strategy_execution(dependencies)
