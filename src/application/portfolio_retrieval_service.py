"""Application-owned portfolio source selection and merge policy."""

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any

from domain.portfolio.scope import (
    PORTFOLIO_SCOPE_ALL,
    PORTFOLIO_SCOPE_KIS,
    PORTFOLIO_SCOPE_TOSS,
    normalize_portfolio_scope,
)


def _empty_source() -> dict[str, Any]:
    return {"accounts": {}, "holdings": [], "asset_info": {}, "cash_holdings": []}


class PortfolioRetrievalService:
    """Select, refresh, and merge portfolio sources through injected ports."""

    def __init__(
        self,
        *,
        fetch_kis: Callable[[], tuple[dict[str, Any], dict[str, Any]]],
        fetch_toss: Callable[[], tuple[dict[str, Any], str | None]],
        get_cached_gsheet: Callable[[], tuple[dict[str, Any], str | None]],
        fetch_toss_exchange_rate: Callable[[], tuple[float | None, str | None]],
        fetch_toss_prices: Callable[[Iterable[str]], dict[str, float]],
        publish_alert: Callable[[str, str], None],
        publish_warning: Callable[[str], None],
        toss_account_key: str,
    ) -> None:
        self._fetch_kis = fetch_kis
        self._fetch_toss = fetch_toss
        self._get_cached_gsheet = get_cached_gsheet
        self._fetch_toss_exchange_rate = fetch_toss_exchange_rate
        self._fetch_toss_prices = fetch_toss_prices
        self._publish_alert = publish_alert
        self._publish_warning = publish_warning
        self._toss_account_key = toss_account_key

    def fetch(self, *, scope: str) -> dict[str, Any]:
        """Return the established normalized source result for one scope."""
        scope = normalize_portfolio_scope(scope)
        kis = _empty_source()
        kis_raw: dict[str, Any] = {"exchange_rate": None, "error": None}
        if scope in {PORTFOLIO_SCOPE_ALL, PORTFOLIO_SCOPE_KIS}:
            kis, kis_raw = self._fetch_kis()

        gsheet = _empty_source()
        gsheet_error = None
        toss_error = None
        exchange_rate = kis_raw.get("exchange_rate")

        if scope == PORTFOLIO_SCOPE_TOSS:
            gsheet, toss_error = self._fetch_toss()
            if not toss_error:
                exchange_rate, exchange_error = self._fetch_toss_exchange_rate()
                if exchange_error:
                    toss_error = exchange_error
                    self._publish_alert(f"Toss Exchange Warning: {exchange_error}", "WARN")
        elif scope == PORTFOLIO_SCOPE_ALL:
            self._publish_alert("[Data] Loading cached GSheet data...", "INFO")
            gsheet, gsheet_error = self._get_cached_gsheet()
            self._discard_current_prices(gsheet)
            if gsheet_error:
                self._publish_alert(f"GSheet Warning: {gsheet_error}", "WARN")
            toss, toss_error = self._fetch_toss()
            if not toss_error:
                gsheet = self._replace_account_source(gsheet, toss, self._toss_account_key)
            self._fill_missing_prices(gsheet)

        return self.merge_sources(
            kis, gsheet, exchange_rate, kis_raw.get("error"), gsheet_error, toss_error
        )

    @staticmethod
    def merge_sources(
        kis: dict[str, Any],
        gsheet: dict[str, Any],
        exchange_rate: float | None,
        kis_error: str | None,
        gsheet_error: str | None,
        toss_error: str | None = None,
    ) -> dict[str, Any]:
        accounts_raw = {**kis.get("accounts", {}), **gsheet.get("accounts", {})}
        id_map = {key: f"acc_{index:02d}" for index, key in enumerate(accounts_raw, 1)}
        accounts = [
            {"id": id_map[key], "name": account["name"]} for key, account in accounts_raw.items()
        ]
        holdings = [
            {
                "account_id": id_map.get(holding["account_key"], "unknown"),
                "ticker": holding["ticker"],
                "name": holding.get("name", holding["ticker"]),
                "qty": holding["qty"],
                "avg_price": holding["avg_price"],
                "cur_price": holding.get("cur_price", holding["avg_price"]),
            }
            for holding in kis.get("holdings", []) + gsheet.get("holdings", [])
        ]
        metadata: dict[str, Any] = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "exchange_rate": exchange_rate,
        }
        for key, error in (
            ("kis_error", kis_error),
            ("gsheet_error", gsheet_error),
            ("toss_error", toss_error),
        ):
            if error:
                metadata[key] = error
        return {
            "metadata": metadata,
            "accounts": accounts,
            "asset_info": {**kis.get("asset_info", {}), **gsheet.get("asset_info", {})},
            "holdings": holdings,
            "cash_holdings": [
                {**cash, "account_id": id_map.get(cash.get("account_key"), "unknown")}
                for cash in kis.get("cash_holdings", []) + gsheet.get("cash_holdings", [])
            ],
        }

    @staticmethod
    def _discard_current_prices(source: dict[str, Any]) -> None:
        for holding in source.get("holdings", []):
            holding.pop("cur_price", None)

    @staticmethod
    def _positive_float(value: Any) -> float:
        try:
            result = float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return 0.0
        return result if result > 0 else 0.0

    @staticmethod
    def _replace_account_source(
        base: dict[str, Any], replacement: dict[str, Any], account_key: str
    ) -> dict[str, Any]:
        result = {
            "accounts": dict(base.get("accounts", {})),
            "holdings": [
                item for item in base.get("holdings", []) if item.get("account_key") != account_key
            ],
            "asset_info": dict(base.get("asset_info", {})),
            "cash_holdings": [
                item
                for item in base.get("cash_holdings", [])
                if item.get("account_key") != account_key
            ],
        }
        result["accounts"].pop(account_key, None)
        tickers = {holding.get("ticker") for holding in result["holdings"]}
        result["asset_info"] = {
            ticker: item for ticker, item in result["asset_info"].items() if ticker in tickers
        }
        for key in ("accounts", "asset_info"):
            result[key].update(replacement.get(key, {}))
        for key in ("holdings", "cash_holdings"):
            result[key].extend(replacement.get(key, []))
        return result

    def _fill_missing_prices(self, source: dict[str, Any]) -> None:
        holdings = [
            item
            for item in source.get("holdings", [])
            if self._positive_float(item.get("cur_price")) <= 0
        ]
        prices = self._fetch_toss_prices(item.get("ticker", "") for item in holdings)
        missing = []
        for holding in holdings:
            symbol = str(holding.get("ticker", "")).strip().upper()
            holding["cur_price"] = prices.get(symbol, 0.0)
            if symbol and holding["cur_price"] <= 0:
                missing.append(symbol)
        if missing:
            self._publish_warning(
                "[Portfolio] Toss current price missing for "
                f"{', '.join(sorted(set(missing)))}; cur_price set to 0"
            )
