"""Google Sheets source adapter for external portfolio holdings."""

import os
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from core.constants import CONFIG_ROOT

SERVICE_ACCOUNT_FILE = os.path.join(CONFIG_ROOT, "service-account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]
SPREADSHEET_NAME = "financial portfolio"


def _normalize_account_name(raw_name: str) -> str:
    """Create a normalized account name for source records."""
    return raw_name.strip()


def connect_google_sheet(sheet_name: str):
    """Connect to a configured Google Sheets worksheet."""
    try:
        credentials = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
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
