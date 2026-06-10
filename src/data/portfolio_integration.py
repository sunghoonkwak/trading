# -*- coding: utf-8 -*-
"""Portfolio source integration owned by the data layer."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


OWNERS = [
    {"id": "owner_01", "name": "곽성훈"},
    {"id": "owner_02", "name": "염인선"},
]


def _empty_source() -> Dict[str, Any]:
    return {
        "accounts": {},
        "holdings": [],
        "asset_info": {},
        "cash_holdings": [],
    }


def _fetch_kis_portfolio() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Fetch KIS holdings and convert them to the standard source format."""
    from core.display import add_alert
    from kis.portfolio_manager import PortfolioManager

    add_alert("[KIS] Fetching KIS API data...", "INFO")
    kis_raw_data = PortfolioManager._fetch_kis_account_data()

    if kis_raw_data.get("error"):
        add_alert(f"KIS Error: {kis_raw_data['error']}", "WARN")
        return _empty_source(), kis_raw_data

    kis_portfolio = PortfolioManager._convert_kis_to_standard(kis_raw_data)
    add_alert(
        f"[KIS] {len(kis_portfolio.get('holdings', []))} holdings loaded",
        "SUCCESS",
    )
    return kis_portfolio, kis_raw_data


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


def merge_portfolio_sources(
    kis: Dict[str, Any],
    gsheet: Dict[str, Any],
    exchange_rate: float,
    kis_error: Optional[str],
    gsheet_error: Optional[str],
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
                "owner_id": account["owner_id"],
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

    return {
        "metadata": metadata,
        "owners": OWNERS,
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

    kis_portfolio, kis_raw_data = _fetch_kis_portfolio()

    gsheet_data = _empty_source()
    gsheet_error = None
    if not kis_only:
        add_alert("[Data] Fetching GSheet data...", "INFO")
        gsheet_data, gsheet_error = fetch_gsheet_portfolio()
        if gsheet_error:
            add_alert(f"GSheet Warning: {gsheet_error}", "WARN")

    return merge_portfolio_sources(
        kis_portfolio,
        gsheet_data,
        kis_raw_data.get("exchange_rate"),
        kis_raw_data.get("error"),
        gsheet_error,
    )
