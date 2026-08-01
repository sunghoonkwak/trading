# -*- coding: utf-8 -*-
"""Infrastructure adapters for the application-owned portfolio merge policy."""

import logging
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from application.portfolio_retrieval_service import PortfolioRetrievalService
from domain.portfolio.scope import PORTFOLIO_SCOPE_ALL
from infrastructure.portfolio.kis_source import fetch_kis_portfolio_source


class IntegratedPortfolioSource:
    """Application-facing adapter for KIS, Toss, and GSheet portfolio data."""

    def fetch(self, *, scope: str) -> Dict[str, Any]:
        return get_integrated_portfolio(scope=scope)


def _empty_source() -> Dict[str, Any]:
    return {
        "accounts": {},
        "holdings": [],
        "asset_info": {},
        "cash_holdings": [],
    }


def invalidate_gsheet_cache() -> None:
    """Clear the GSheet adapter cache through the compatibility seam."""
    from infrastructure.gsheet.portfolio_source import invalidate_portfolio_cache

    invalidate_portfolio_cache()


def fetch_gsheet_portfolio() -> Tuple[Dict[str, Any], Optional[str]]:
    """Fetch GSheet data through the adapter compatibility seam."""
    from infrastructure.gsheet.portfolio_source import fetch_portfolio

    return fetch_portfolio()


def refresh_gsheet_cache() -> Dict[str, Any]:
    """Refresh the GSheet adapter cache through the compatibility seam."""
    from infrastructure.gsheet.portfolio_source import refresh_portfolio_cache

    return refresh_portfolio_cache(fetch_gsheet_portfolio)


def get_cached_gsheet_portfolio() -> Tuple[Dict[str, Any], Optional[str]]:
    """Read the GSheet adapter cache through the compatibility seam."""
    from infrastructure.gsheet.portfolio_source import get_cached_portfolio

    return get_cached_portfolio(fetch_gsheet_portfolio)


def fetch_toss_exchange_rate() -> Tuple[Optional[float], Optional[str]]:
    """Fetch the Toss USD/KRW rate used for Toss-only portfolio valuation."""
    try:
        from infrastructure.toss.auth import load_access_token
        from infrastructure.toss.get_exchange_rate import get_exchange_rate

        result = get_exchange_rate(
            base_currency="USD",
            quote_currency="KRW",
            access_token=load_access_token(),
        )
        return float(str(result.get("rate", "")).replace(",", "")), None
    except Exception as error:
        return None, str(error)


def fetch_toss_portfolio_source() -> Tuple[Dict[str, Any], Optional[str]]:
    """Fetch Toss source data and emit portfolio alerts."""
    from infrastructure.toss.portfolio import fetch_toss_portfolio

    try:
        _publish_alert("[Toss] Fetching Toss API data...", "INFO")
        toss_data, toss_error = fetch_toss_portfolio()
        if toss_error:
            _publish_alert(f"Toss Warning: {toss_error}", "WARN")
        else:
            _publish_alert(
                f"[Toss] {len(toss_data.get('holdings', []))} holdings loaded",
                "SUCCESS",
            )
        return toss_data, toss_error
    except Exception as error:
        toss_error = str(error)
        _publish_alert(f"Toss Warning: {toss_error}", "WARN")
        return _empty_source(), toss_error


def _to_positive_float(value: Any) -> float:
    try:
        price = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0
    return price if price > 0 else 0.0


def fetch_toss_prices(tickers: Iterable[str]) -> Dict[str, float]:
    """Fetch current prices from Toss market data without KIS fallback."""
    symbols = sorted(
        {
            str(ticker).strip().upper()
            for ticker in tickers
            if str(ticker).strip()
        }
    )
    if not symbols:
        return {}

    try:
        from infrastructure.toss.auth import load_access_token
        from infrastructure.toss.get_prices import get_prices

        access_token = load_access_token()
        prices: Dict[str, float] = {}
        for start in range(0, len(symbols), 200):
            for item in get_prices(symbols[start:start + 200], access_token=access_token):
                symbol = str(item.get("symbol", "")).strip().upper()
                price = _to_positive_float(item.get("lastPrice"))
                if symbol and price > 0:
                    prices[symbol] = price
        return prices
    except Exception as error:
        logging.warning("[Portfolio] Toss current price fetch failed: %s", error)
        return {}


_warning_notifier = None
_alert_publisher: Optional[Callable[[str, str], None]] = None


def configure_alert_publisher(
    publisher: Optional[Callable[[str, str], None]],
) -> None:
    """Inject local portfolio alert delivery at composition time."""
    global _alert_publisher
    _alert_publisher = publisher


def _publish_alert(message: str, level: str) -> None:
    if _alert_publisher is None:
        return
    try:
        _alert_publisher(message, level)
    except Exception as error:
        logging.warning("[Portfolio] Alert publication failed: %s", error)


def configure_warning_notifier(notifier) -> None:
    """Inject optional operator notification delivery at composition time."""
    global _warning_notifier
    _warning_notifier = notifier


def send_telegram_warning(message: str) -> None:
    """Send a portfolio warning to Telegram and the local alert stream."""
    _publish_alert(message, "WARNING")
    if _warning_notifier is not None:
        try:
            _warning_notifier(message)
        except Exception as error:
            logging.warning("[Portfolio] Telegram warning failed: %s", error)


def _build_portfolio_retrieval_service() -> PortfolioRetrievalService:
    from infrastructure.toss.portfolio import TOSS_ACCOUNT_KEY

    return PortfolioRetrievalService(
        fetch_kis=fetch_kis_portfolio_source,
        fetch_toss=fetch_toss_portfolio_source,
        get_cached_gsheet=get_cached_gsheet_portfolio,
        fetch_toss_exchange_rate=fetch_toss_exchange_rate,
        fetch_toss_prices=fetch_toss_prices,
        publish_alert=_publish_alert,
        publish_warning=send_telegram_warning,
        toss_account_key=TOSS_ACCOUNT_KEY,
    )


def get_integrated_portfolio(scope: str = PORTFOLIO_SCOPE_ALL) -> Dict[str, Any]:
    """Fetch portfolio data through the single application merge policy."""
    return _build_portfolio_retrieval_service().fetch(scope=scope)
