"""Google Sheets source adapter and cache for external portfolio holdings."""

import logging
import threading
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

import gspread
from google.oauth2.service_account import Credentials

_service_account_file: Optional[str] = None
_portfolio_cache_lock = threading.Lock()
_portfolio_cache: Optional[Dict[str, Any]] = None
_portfolio_cache_error: Optional[str] = None
_portfolio_cache_updated_at: Optional[datetime] = None
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]
SPREADSHEET_NAME = "financial portfolio"


def configure_service_account_file(path: Optional[str]) -> None:
    """Inject the private Google service-account file path."""
    global _service_account_file
    _service_account_file = path


def _normalize_account_name(raw_name: str) -> str:
    """Create a normalized account name for source records."""
    return raw_name.strip()


def connect_google_sheet(sheet_name: str):
    """Connect to a configured Google Sheets worksheet."""
    try:
        if _service_account_file is None:
            raise RuntimeError("Google service-account file is not configured")
        credentials = Credentials.from_service_account_file(
            _service_account_file,
            scopes=SCOPES,
        )
        client = gspread.authorize(credentials)
        spreadsheet = client.open(SPREADSHEET_NAME)
        return spreadsheet.worksheet(sheet_name)
    except Exception as error:
        print(f"Failed to connect to Google Sheets ({sheet_name}): {error}")
        return None


def parse_worksheet_data(worksheet: Any, currency: str) -> dict[str, Any]:
    """Parse a worksheet into the established normalized portfolio source."""
    holdings = []
    accounts = {}
    asset_info = {}
    cash_holdings = []

    for row in worksheet.get_all_values()[2:]:
        if len(row) < 6:
            continue

        ticker = row[0].strip()
        stock_name = row[1].strip()
        qty_text = row[2].strip().replace(",", "")
        average_price_text = (
            row[3]
            .strip()
            .replace(",", "")
            .replace("$", "")
            .replace("₩", "")
            .replace("\\", "")
        )
        raw_account_name = row[5].strip()
        if not ticker or not raw_account_name:
            continue

        try:
            quantity = float(qty_text) if qty_text else 0.0
            average_price = float(average_price_text) if average_price_text else 0.0
        except ValueError:
            continue

        account_name = _normalize_account_name(raw_account_name)
        accounts.setdefault(account_name, {"name": account_name})
        if "예수금" in ticker or "예수금" in stock_name:
            cash_holdings.append(
                {
                    "account_name": account_name,
                    "account_key": account_name,
                    "amount": quantity,
                    "currency": currency,
                }
            )
            continue
        if quantity <= 0:
            continue

        asset_info.setdefault(
            ticker,
            {
                "name": stock_name or ticker,
                "market": "US" if currency == "USD" else "KR",
                "asset_type": "Stock",
                "currency": currency,
            },
        )
        holdings.append(
            {
                "account_key": account_name,
                "ticker": ticker,
                "name": stock_name or ticker,
                "qty": quantity,
                "avg_price": average_price,
            }
        )

    return {
        "holdings": holdings,
        "accounts": accounts,
        "asset_info": asset_info,
        "cash_holdings": cash_holdings,
    }


def _empty_source() -> Dict[str, Any]:
    return {
        "accounts": {},
        "holdings": [],
        "asset_info": {},
        "cash_holdings": [],
    }


def fetch_portfolio() -> Tuple[Dict[str, Any], Optional[str]]:
    """Fetch passive portfolio holdings from Google Sheets."""
    source = _empty_source()
    errors = []
    for currency in ["USD", "KRW"]:
        sheet = connect_google_sheet(currency)
        if sheet:
            parsed = parse_worksheet_data(sheet, currency)
            source["accounts"].update(parsed["accounts"])
            source["holdings"].extend(parsed["holdings"])
            source["asset_info"].update(parsed["asset_info"])
            source["cash_holdings"].extend(parsed["cash_holdings"])
        else:
            errors.append(f"Failed to connect {currency} sheet")

    return source, " | ".join(errors) if errors else None


def invalidate_portfolio_cache() -> None:
    """Clear the in-memory Google Sheets portfolio cache."""
    global _portfolio_cache, _portfolio_cache_error, _portfolio_cache_updated_at

    with _portfolio_cache_lock:
        _portfolio_cache = None
        _portfolio_cache_error = None
        _portfolio_cache_updated_at = None


def refresh_portfolio_cache(
    fetcher: Callable[[], Tuple[Dict[str, Any], Optional[str]]] = fetch_portfolio,
) -> Dict[str, Any]:
    """Refresh the Google Sheets cache and retain the last safe source on failure."""
    global _portfolio_cache, _portfolio_cache_error, _portfolio_cache_updated_at

    try:
        source, error = fetcher()
    except Exception as error:
        logging.warning("[Portfolio] GSheet cache refresh failed: %s", error)
        with _portfolio_cache_lock:
            _portfolio_cache_error = str(error)
            if _portfolio_cache is None:
                _portfolio_cache = _empty_source()
            cached = deepcopy(_portfolio_cache)
            cached_at = _portfolio_cache_updated_at
        return {
            "success": False,
            "holdings_count": len(cached.get("holdings", [])),
            "cash_count": len(cached.get("cash_holdings", [])),
            "accounts_count": len(cached.get("accounts", {})),
            "error": str(error),
            "last_updated": cached_at.isoformat() if cached_at else None,
        }

    updated_at = datetime.now(timezone.utc)
    with _portfolio_cache_lock:
        _portfolio_cache = deepcopy(source)
        _portfolio_cache_error = error
        _portfolio_cache_updated_at = updated_at

    return {
        "success": error is None,
        "holdings_count": len(source.get("holdings", [])),
        "cash_count": len(source.get("cash_holdings", [])),
        "accounts_count": len(source.get("accounts", {})),
        "error": error,
        "last_updated": updated_at.isoformat(),
    }


def get_cached_portfolio(
    fetcher: Callable[[], Tuple[Dict[str, Any], Optional[str]]] = fetch_portfolio,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Return cached Google Sheets data, loading it once when needed."""
    with _portfolio_cache_lock:
        cached = deepcopy(_portfolio_cache) if _portfolio_cache is not None else None
        error = _portfolio_cache_error

    if cached is None:
        refresh_portfolio_cache(fetcher)
        with _portfolio_cache_lock:
            cached = (
                deepcopy(_portfolio_cache)
                if _portfolio_cache is not None
                else _empty_source()
            )
            error = _portfolio_cache_error

    return cached, error
