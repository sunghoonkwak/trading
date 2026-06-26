# -*- coding: utf-8 -*-
"""Portfolio source integration owned by the data layer."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

from data.portfolio_scope import (
    PORTFOLIO_SCOPE_ALL,
    PORTFOLIO_SCOPE_KIS,
    PORTFOLIO_SCOPE_TOSS,
    normalize_portfolio_scope,
)


def _empty_source() -> Dict[str, Any]:
    return {
        "accounts": {},
        "holdings": [],
        "asset_info": {},
        "cash_holdings": [],
    }


def fetch_gsheet_portfolio() -> Tuple[Dict[str, Any], Optional[str]]:
    """Fetch passive portfolio holdings from Google Sheets."""
    from data.gsheet import connect_google_sheet, parse_worksheet_data

    gs_data = _empty_source()
    errors = []
    for currency in ["USD", "KRW"]:
        sheet = connect_google_sheet(currency)
        if sheet:
            parsed = parse_worksheet_data(sheet, currency)
            gs_data["accounts"].update(parsed["accounts"])
            gs_data["holdings"].extend(parsed["holdings"])
            gs_data["asset_info"].update(parsed["asset_info"])
            gs_data["cash_holdings"].extend(parsed["cash_holdings"])
        else:
            errors.append(f"Failed to connect {currency} sheet")

    return gs_data, " | ".join(errors) if errors else None


def fetch_toss_exchange_rate() -> Tuple[Optional[float], Optional[str]]:
    """Fetch the Toss USD/KRW rate used for Toss-only portfolio valuation."""
    try:
        from toss.auth import load_access_token
        from toss.get_exchange_rate import get_exchange_rate

        result = get_exchange_rate(
            base_currency="USD",
            quote_currency="KRW",
            access_token=load_access_token(),
        )
        return float(str(result.get("rate", "")).replace(",", "")), None
    except Exception as e:
        return None, str(e)


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
        from toss.auth import load_access_token
        from toss.get_prices import get_prices

        access_token = load_access_token()
        prices: Dict[str, float] = {}
        for start in range(0, len(symbols), 200):
            batch = symbols[start:start + 200]
            for item in get_prices(batch, access_token=access_token):
                symbol = str(item.get("symbol", "")).strip().upper()
                price = _to_positive_float(item.get("lastPrice"))
                if symbol and price > 0:
                    prices[symbol] = price
        return prices
    except Exception as e:
        logging.warning("[Portfolio] Toss current price fetch failed: %s", e)
        return {}


def send_telegram_warning(message: str) -> None:
    """Send a portfolio warning to Telegram and the local alert stream."""
    from core.display import add_alert

    add_alert(message, "WARNING")
    try:
        from telegram_bot.telegram_utils import send_notification

        send_notification(message)
    except Exception as e:
        logging.warning("[Portfolio] Telegram warning failed: %s", e)


def discard_source_current_prices(source: Dict[str, Any]) -> None:
    """Remove GSheet current prices so live Toss prices are authoritative."""
    for holding in source.get("holdings", []):
        holding.pop("cur_price", None)


def fill_missing_current_prices_from_toss(source: Dict[str, Any]) -> None:
    """Fill holdings that do not already have broker current prices."""
    holdings = [
        holding
        for holding in source.get("holdings", [])
        if _to_positive_float(holding.get("cur_price")) <= 0
    ]
    if not holdings:
        return

    prices = fetch_toss_prices(holding.get("ticker", "") for holding in holdings)
    missing = []
    for holding in holdings:
        ticker = str(holding.get("ticker", "")).strip()
        symbol = ticker.upper()
        price = prices.get(symbol, 0.0)
        if price > 0:
            holding["cur_price"] = price
        else:
            holding["cur_price"] = 0.0
            if symbol:
                missing.append(symbol)

    if missing:
        symbols = ", ".join(sorted(set(missing)))
        send_telegram_warning(
            f"[Portfolio] Toss current price missing for {symbols}; cur_price set to 0"
        )


def replace_account_source(
    base: Dict[str, Any],
    replacement: Dict[str, Any],
    account_key: str,
) -> Dict[str, Any]:
    """Replace one account's standardized source records inside a source."""
    result = {
        "accounts": dict(base.get("accounts", {})),
        "holdings": [
            holding
            for holding in base.get("holdings", [])
            if holding.get("account_key") != account_key
        ],
        "asset_info": dict(base.get("asset_info", {})),
        "cash_holdings": [
            cash
            for cash in base.get("cash_holdings", [])
            if cash.get("account_key") != account_key
        ],
    }

    result["accounts"].pop(account_key, None)

    kept_tickers = {holding.get("ticker") for holding in result["holdings"]}
    result["asset_info"] = {
        ticker: info
        for ticker, info in result["asset_info"].items()
        if ticker in kept_tickers
    }

    result["accounts"].update(replacement.get("accounts", {}))
    result["holdings"].extend(replacement.get("holdings", []))
    result["asset_info"].update(replacement.get("asset_info", {}))
    result["cash_holdings"].extend(replacement.get("cash_holdings", []))
    return result


def merge_portfolio_sources(
    kis: Dict[str, Any],
    gsheet: Dict[str, Any],
    exchange_rate: float,
    kis_error: Optional[str],
    gsheet_error: Optional[str],
    toss_error: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge standardized KIS and GSheet sources into raw portfolio data."""
    all_accounts_raw = {
        **kis.get("accounts", {}),
        **gsheet.get("accounts", {}),
    }
    account_list = []
    id_map = {}
    for idx, (key, account) in enumerate(all_accounts_raw.items(), start=1):
        account_id = f"acc_{idx:02d}"
        id_map[key] = account_id
        account_list.append(
            {
                "id": account_id,
                "name": account["name"],
            }
        )

    holdings = []
    for holding in kis.get("holdings", []) + gsheet.get("holdings", []):
        holdings.append(
            {
                "account_id": id_map.get(holding["account_key"], "unknown"),
                "ticker": holding["ticker"],
                "name": holding.get("name", holding["ticker"]),
                "qty": holding["qty"],
                "avg_price": holding["avg_price"],
                "cur_price": holding.get("cur_price", holding["avg_price"]),
            }
        )

    cash_holdings = []
    for cash in kis.get("cash_holdings", []) + gsheet.get("cash_holdings", []):
        cash_holdings.append(
            {
                **cash,
                "account_id": id_map.get(cash.get("account_key"), "unknown"),
            }
        )

    metadata = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "exchange_rate": exchange_rate,
    }
    if kis_error:
        metadata["kis_error"] = kis_error
    if gsheet_error:
        metadata["gsheet_error"] = gsheet_error
    if toss_error:
        metadata["toss_error"] = toss_error

    return {
        "metadata": metadata,
        "accounts": account_list,
        "asset_info": {
            **kis.get("asset_info", {}),
            **gsheet.get("asset_info", {}),
        },
        "holdings": holdings,
        "cash_holdings": cash_holdings,
    }


def get_integrated_portfolio(scope: str = PORTFOLIO_SCOPE_ALL) -> Dict[str, Any]:
    """Fetch and merge portfolio sources for application data consumers."""
    from core.display import add_alert

    scope = normalize_portfolio_scope(scope)

    kis_portfolio = _empty_source()
    kis_raw_data = {"exchange_rate": None, "error": None}
    if scope in {PORTFOLIO_SCOPE_ALL, PORTFOLIO_SCOPE_KIS}:
        from broker.portfolio import fetch_kis_source

        kis_portfolio, kis_raw_data = fetch_kis_source()

    gsheet_data = _empty_source()
    gsheet_error = None
    toss_error = None
    exchange_rate = kis_raw_data.get("exchange_rate")

    if scope == PORTFOLIO_SCOPE_TOSS:
        from broker.portfolio import fetch_toss_source

        try:
            add_alert("[Toss] Fetching Toss API data...", "INFO")
            gsheet_data, toss_error = fetch_toss_source()
            if toss_error:
                add_alert(f"Toss Warning: {toss_error}", "WARN")
            else:
                add_alert(
                    f"[Toss] {len(gsheet_data.get('holdings', []))} holdings loaded",
                    "SUCCESS",
                )
        except Exception as e:
            toss_error = str(e)
            add_alert(f"Toss Warning: {toss_error}", "WARN")

        if not toss_error:
            exchange_rate, exchange_error = fetch_toss_exchange_rate()
            if exchange_error:
                toss_error = " | ".join(filter(None, [toss_error, exchange_error]))
                add_alert(f"Toss Exchange Warning: {exchange_error}", "WARN")

    elif scope == PORTFOLIO_SCOPE_ALL:
        from broker.portfolio import TOSS_ACCOUNT_KEY, fetch_toss_source

        add_alert("[Data] Fetching GSheet data...", "INFO")
        gsheet_data, gsheet_error = fetch_gsheet_portfolio()
        discard_source_current_prices(gsheet_data)
        if gsheet_error:
            add_alert(f"GSheet Warning: {gsheet_error}", "WARN")
        try:
            add_alert("[Toss] Fetching Toss API data...", "INFO")
            toss_data, toss_error = fetch_toss_source()
            if toss_error:
                add_alert(f"Toss Warning: {toss_error}", "WARN")
            else:
                gsheet_data = replace_account_source(
                    gsheet_data,
                    toss_data,
                    TOSS_ACCOUNT_KEY,
                )
                add_alert(
                    f"[Toss] {len(toss_data.get('holdings', []))} holdings loaded",
                    "SUCCESS",
                )
        except Exception as e:
            toss_error = str(e)
            add_alert(f"Toss Warning: {toss_error}", "WARN")

        fill_missing_current_prices_from_toss(gsheet_data)

    return merge_portfolio_sources(
        kis_portfolio,
        gsheet_data,
        exchange_rate,
        kis_raw_data.get("error"),
        gsheet_error,
        toss_error,
    )
