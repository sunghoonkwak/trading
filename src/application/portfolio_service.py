"""Portfolio retrieval use case with injected infrastructure collaborators."""

import logging
from collections.abc import Callable
from typing import Any

from application.ports import PortfolioSource
from domain.portfolio.processing import PortfolioProcessor
from domain.portfolio.scope import (
    PORTFOLIO_SCOPE_ALL,
    PORTFOLIO_SCOPE_KIS,
    normalize_portfolio_scope,
)


class PortfolioService:
    """Assemble the established portfolio result without concrete imports."""

    def __init__(
        self,
        *,
        is_kis_ready: Callable[[], bool],
        portfolio_source: PortfolioSource,
        save_portfolio: Callable[[dict[str, Any]], None],
        load_weights: Callable[[], dict[str, Any]],
        calculate_targets: Callable[..., tuple[dict[str, float], Any, Any]],
        fear_and_greed: Callable[[], Any],
        publish_alert: Callable[[str, str], None],
    ) -> None:
        self._is_kis_ready = is_kis_ready
        self._portfolio_source = portfolio_source
        self._save_portfolio = save_portfolio
        self._load_weights = load_weights
        self._calculate_targets = calculate_targets
        self._fear_and_greed = fear_and_greed
        self._publish_alert = publish_alert

    def get_portfolio_data(self, force_refresh: bool = False, scope: str = "all") -> dict[str, Any]:
        scope = normalize_portfolio_scope(scope)
        if not self._is_kis_ready():
            return {"error": "KIS Thread not ready"}

        self._publish_alert("[Data] Fetching portfolio...", "INFO")
        raw_portfolio = self._portfolio_source.fetch(scope=scope)
        self._save_portfolio(raw_portfolio)
        processor = PortfolioProcessor()
        merged_data, total_usd = processor.merge_holdings(raw_portfolio)
        result = {
            "raw": raw_portfolio,
            "merged_data": merged_data,
            "total_value_usd": total_usd,
            "stats": processor.calculate_stats(raw_portfolio),
            "exchange_rate": raw_portfolio.get("metadata", {}).get("exchange_rate"),
            "price_map": {
                ticker: data["cur_price"]
                for ticker, data in merged_data.items()
                if data["type"] == "STOCK"
            },
            "accounts": raw_portfolio.get("accounts", []),
            "holdings": raw_portfolio.get("holdings", []),
            "metadata": raw_portfolio.get("metadata", {}),
        }
        try:
            current_weights = {
                ticker: data["current_value_usd"] / total_usd
                for ticker, data in merged_data.items()
                if total_usd > 0
            }
            result["current_weights"] = current_weights
            result["targets"], _, _ = self._calculate_targets(
                current_weights, self._load_weights(), self._fear_and_greed()
            )
        except Exception as exc:
            logging.error("Weight calc error: %s", exc)
            result["targets"] = {}

        level = "WARN" if any(result["metadata"].get(key) for key in ("gsheet_error", "kis_error")) else "SUCCESS"
        message = "[Data] Portfolio loaded (partial)" if level == "WARN" else "[Data] Portfolio loaded"
        self._publish_alert(message, level)
        return self.apply_scope_filter(result, scope)

    @staticmethod
    def apply_scope_filter(data: dict[str, Any], scope: str) -> dict[str, Any]:
        scope = normalize_portfolio_scope(scope)
        if scope == PORTFOLIO_SCOPE_ALL:
            return data
        raw = data["raw"]
        accounts = raw.get("accounts", [])
        target_name = "한국투자증권" if scope == PORTFOLIO_SCOPE_KIS else "토스"
        target_ids = {account["id"] for account in accounts if account.get("name") == target_name}
        target_names = {account["name"] for account in accounts if account["id"] in target_ids}
        filtered_raw = {
            "metadata": raw.get("metadata", {}),
            "asset_info": raw.get("asset_info", {}),
            "holdings": [holding for holding in raw.get("holdings", []) if holding.get("account_id") in target_ids],
            "cash_holdings": [
                cash for cash in raw.get("cash_holdings", [])
                if cash.get("account_id") in target_ids or cash.get("account_name") in target_names
            ],
        }
        processor = PortfolioProcessor()
        merged, total = processor.merge_holdings(filtered_raw)
        scoped = dict(data)
        scoped.update(
            merged_data=merged,
            total_value_usd=total,
            stats=processor.calculate_stats(filtered_raw),
            holdings=filtered_raw["holdings"],
            current_weights={
                ticker: entry["current_value_usd"] / total
                for ticker, entry in merged.items()
                if total > 0
            },
        )
        return scoped
