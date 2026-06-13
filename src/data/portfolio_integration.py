# -*- coding: utf-8 -*-
"""Portfolio source integration owned by the data layer."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


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


def get_integrated_portfolio(kis_only: bool = False) -> Dict[str, Any]:
    """Fetch and merge portfolio sources for application data consumers."""
    from core.display import add_alert
    from broker.portfolio import fetch_kis_source

    kis_portfolio, kis_raw_data = fetch_kis_source()

    gsheet_data = _empty_source()
    gsheet_error = None
    toss_error = None
    if not kis_only:
        from broker.portfolio import TOSS_ACCOUNT_KEY, fetch_toss_source

        add_alert("[Data] Fetching GSheet data...", "INFO")
        gsheet_data, gsheet_error = fetch_gsheet_portfolio()
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

    return merge_portfolio_sources(
        kis_portfolio,
        gsheet_data,
        kis_raw_data.get("exchange_rate"),
        kis_raw_data.get("error"),
        gsheet_error,
        toss_error,
    )
