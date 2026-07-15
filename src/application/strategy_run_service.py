"""Application use cases for running configured trading strategies."""

from collections.abc import Callable
from typing import Any


class StrategyHistoryPersistenceError(RuntimeError):
    """Raised when durable strategy history cannot be saved."""


class StrategyRunService:
    """Expose strategy runs without binding callers to broker infrastructure."""

    def __init__(
        self,
        *,
        run_raoeo: Callable[..., dict[str, Any]],
        run_value_averaging: Callable[..., dict[str, Any]],
        run_rebalancing: Callable[..., dict[str, Any]],
        run_suite: Callable[..., tuple[dict[str, Any], dict[str, Any]]] | None = None,
    ) -> None:
        self._run_raoeo = run_raoeo
        self._run_value_averaging = run_value_averaging
        self._run_rebalancing = run_rebalancing
        self._run_suite = run_suite

    def run_raoeo(self, *, execute: bool = False, **kwargs: Any) -> dict[str, Any]:
        """Run the configured RAOEO strategy."""
        return self._run_raoeo(execute=execute, **kwargs)

    def run_value_averaging(self, *, execute: bool = False, **kwargs: Any) -> dict[str, Any]:
        """Run the configured value-averaging strategy."""
        return self._run_value_averaging(execute=execute, **kwargs)

    def run_rebalancing(self, *, execute: bool = False, **kwargs: Any) -> dict[str, Any]:
        """Run the configured rebalancing strategy."""
        return self._run_rebalancing(execute=execute, **kwargs)

    def run_suite(self, *, execute: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
        """Run RAOEO and value averaging through their shared application use case."""
        if self._run_suite is not None:
            return self._run_suite(execute=execute)
        return self.run_raoeo(execute=execute), self.run_value_averaging(execute=execute)


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


class StrategyHistoryService:
    """Manage strategy-history records through injected persistence ports."""

    def __init__(
        self,
        *,
        load: Callable[[], list[dict[str, Any]]],
        save: Callable[[list[dict[str, Any]]], bool],
    ) -> None:
        self._load = load
        self._save = save

    def load_history(self) -> list[dict[str, Any]]:
        """Load the established list-shaped history document."""
        history = self._load()
        if not isinstance(history, list):
            raise ValueError("strategy_history.json must contain a list.")
        return history

    def clear_date(self, target_date: str) -> dict[str, Any]:
        """Remove one date's complete strategy history entry."""
        history = self.load_history()
        updated = [
            entry
            for entry in history
            if not (isinstance(entry, dict) and entry.get("date") == target_date)
        ]
        removed = len(updated) != len(history)
        if removed and not self._save(updated):
            raise RuntimeError("Failed to save strategy_history.json.")
        return {"date": target_date, "removed": removed}

    def save_strategy(
        self,
        date: str,
        strategy_key: str,
        strategy_data: dict[str, Any],
    ) -> None:
        """Upsert one strategy result and retain the newest 200 dates."""
        history = self.load_history()
        entry = next(
            (item for item in history if isinstance(item, dict) and item.get("date") == date),
            None,
        )
        if entry is None:
            entry = {"date": date}
            history.insert(0, entry)
        previous = entry.get(strategy_key, {})
        if strategy_key == "raoeo" and previous.get("cash_funding_results"):
            strategy_data.setdefault("cash_funding_results", previous["cash_funding_results"])
        entry[strategy_key] = strategy_data
        if not self._save(history[:200]):
            raise StrategyHistoryPersistenceError("Failed to save strategy history.")

    def save_cash_funding_result(
        self,
        date: str,
        record: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Upsert a manual RAOEO cash-funding result by correlation ID."""
        history = self.load_history()
        entry = next(
            (item for item in history if isinstance(item, dict) and item.get("date") == date),
            None,
        )
        if entry is None:
            entry = {"date": date}
            history.insert(0, entry)
        raoeo_data = entry.setdefault("raoeo", {"orders": []})
        results = raoeo_data.setdefault("cash_funding_results", [])
        correlation_id = record.get("correlation_id")
        existing = next(
            (
                index
                for index, previous in enumerate(results)
                if correlation_id and previous.get("correlation_id") == correlation_id
            ),
            None,
        )
        if existing is None:
            results.append(record)
        else:
            results[existing] = record
        if not self._save(history[:200]):
            raise StrategyHistoryPersistenceError("Failed to save cash funding history.")
        return results
