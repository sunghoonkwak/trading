"""Application use cases for running configured trading strategies."""

from collections.abc import Callable
from typing import Any


class StrategyRunService:
    """Expose strategy runs without binding callers to broker infrastructure."""

    def __init__(
        self,
        *,
        run_raoeo: Callable[..., dict[str, Any]],
        run_value_averaging: Callable[..., dict[str, Any]],
        run_rebalancing: Callable[..., dict[str, Any]],
    ) -> None:
        self._run_raoeo = run_raoeo
        self._run_value_averaging = run_value_averaging
        self._run_rebalancing = run_rebalancing

    def run_raoeo(self, *, execute: bool = False, **kwargs: Any) -> dict[str, Any]:
        """Run the configured RAOEO strategy."""
        return self._run_raoeo(execute=execute, **kwargs)

    def run_value_averaging(self, *, execute: bool = False, **kwargs: Any) -> dict[str, Any]:
        """Run the configured value-averaging strategy."""
        return self._run_value_averaging(execute=execute, **kwargs)

    def run_rebalancing(self, *, execute: bool = False, **kwargs: Any) -> dict[str, Any]:
        """Run the configured rebalancing strategy."""
        return self._run_rebalancing(execute=execute, **kwargs)


class StrategyMarketDataService:
    """Assemble strategy holdings and prices through injected read ports."""

    def __init__(
        self,
        *,
        load_portfolio: Callable[..., dict[str, Any]],
        load_strategy_config: Callable[[], dict[str, Any]],
        fetch_prices: Callable[[list[str]], dict[str, float]],
        resolve_price: Callable[[str, dict[str, Any], dict[str, float]], float],
        strategy_broker_name: Callable[[], str],
    ) -> None:
        self._load_portfolio = load_portfolio
        self._load_strategy_config = load_strategy_config
        self._fetch_prices = fetch_prices
        self._resolve_price = resolve_price
        self._strategy_broker_name = strategy_broker_name

    def get_market_data(
        self,
        *,
        force_refresh: bool = False,
        include_cash_ticker: bool = False,
    ) -> tuple[dict[str, Any], dict[str, float]]:
        """Load the configured strategy universe and fill missing prices."""
        portfolio = self._load_portfolio(
            force_refresh=force_refresh,
            scope=self._strategy_broker_name(),
        )
        holdings = portfolio.get("merged_data", {})
        config = self._load_strategy_config()
        tickers = set(config.get("raoeo", {}).get("targets", {}))
        tickers.update(config.get("value_averaging", {}).get("targets", {}))
        tickers.update(
            asset["ticker"]
            for asset in config.get("rebalancing", {}).get("assets", [])
        )
        cash_ticker = config.get("cash_ticker", "")
        if include_cash_ticker and cash_ticker:
            tickers.add(cash_ticker)

        prices: dict[str, float] = {}
        missing = []
        for ticker in tickers:
            price = self._resolve_price(ticker, holdings.get(ticker, {}), {})
            if price > 0:
                prices[ticker] = price
            else:
                missing.append(ticker)
        if missing:
            prices.update(self._fetch_prices(missing))
        return holdings, prices
