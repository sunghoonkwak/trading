# -*- coding: utf-8 -*-
"""Broker selector for strategy-owned account operations."""

from typing import Tuple

from data.config_manager import ConfigFile, load_json
from strategy.base import StrategyOrder


KIS_BROKER = "kis"
TOSS_BROKER = "toss"
_ACCOUNT_NAMES = {
    KIS_BROKER: "한국투자증권",
    TOSS_BROKER: "토스",
}


def get_strategy_broker_name() -> str:
    """Return the configured strategy broker name."""
    config = load_json(ConfigFile.STRATEGY_CONFIG, default={})
    broker_name = str(config.get("strategy_broker", KIS_BROKER)).strip().lower()
    if broker_name not in _ACCOUNT_NAMES:
        raise ValueError(
            "strategy_broker must be one of: "
            f"{', '.join(sorted(_ACCOUNT_NAMES))}"
        )
    return broker_name


def get_strategy_account_name() -> str:
    """Return the portfolio account name for the configured strategy broker."""
    return _ACCOUNT_NAMES[get_strategy_broker_name()]


def get_orderable_usd(symbol: str, order_price: float) -> float:
    """Return USD buying power for the configured strategy broker."""
    broker_name = get_strategy_broker_name()
    if broker_name == TOSS_BROKER:
        from broker import toss_broker

        return toss_broker.get_orderable_usd(symbol, order_price)

    from broker import kis_broker

    return kis_broker.get_orderable_usd(symbol, order_price)


def place_order(order: StrategyOrder) -> Tuple[bool, str]:
    """Place a strategy order through the configured strategy broker."""
    broker_name = get_strategy_broker_name()
    if broker_name == TOSS_BROKER:
        from broker import toss_broker

        return toss_broker.place_order(order)

    from broker import kis_broker

    return kis_broker.place_overseas_order(order)
