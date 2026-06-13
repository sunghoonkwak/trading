# -*- coding: utf-8 -*-
"""
Google Sheets data source for external portfolio holdings.
"""
import os

import gspread
from google.oauth2.service_account import Credentials

from core.constants import CONFIG_ROOT

SERVICE_ACCOUNT_FILE = os.path.join(CONFIG_ROOT, "service-account.json")
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]
SPREADSHEET_NAME = 'financial portfolio'

def _normalize_account_name(raw_name: str) -> str:
    """Create normalized account name for unique identification."""
    return raw_name.strip()


def connect_google_sheet(sheet_name: str):
    """Connect to a specific Google Sheets worksheet."""
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        spreadsheet = client.open(SPREADSHEET_NAME)
        worksheet = spreadsheet.worksheet(sheet_name)
        return worksheet
    except Exception as e:
        print(f"Failed to connect to Google Sheets ({sheet_name}): {e}")
        return None


def parse_worksheet_data(worksheet, currency: str) -> dict:
    """
    Parse worksheet data into holdings and accounts.

    GSheet structure:
    - Col A: ticker (stock code like 030200, QQQM)
    - Col B: name (종목명)
    - Col C: qty (보유 수량)
    - Col D: avg_price (평균 단가)
    - Col E: investment (투자금) - calculated, not used
    - Col F: account (계좌)
    - Col G: current_price (현재가)

    Returns:
        dict with 'holdings', 'accounts', 'asset_info', 'cash_holdings'
    """
    all_values = worksheet.get_all_values()

    holdings = []
    accounts = {}
    asset_info = {}
    cash_holdings = []

    # Skip header rows (row 1-2 based on sheet structure)
    for row in all_values[2:]:
        if len(row) < 6:
            continue

        ticker = row[0].strip()  # Col A: ticker code
        stock_name = row[1].strip()  # Col B: name
        qty_str = row[2].strip().replace(',', '')  # Col C: qty
        avg_price_str = row[3].strip().replace(',', '').replace('$', '').replace('₩', '').replace('\\', '')  # Col D: avg_price
        raw_account_name = row[5].strip() if len(row) > 5 else ""  # Col F: account
        cur_price_str = row[6].strip().replace(',', '').replace('$', '').replace('₩', '').replace('\\', '') if len(row) > 6 else ""  # Col G: current_price

        # Skip empty rows
        if not ticker or not raw_account_name:
            continue
        account_name = _normalize_account_name(raw_account_name)

        # Parse quantity and prices
        try:
            qty = float(qty_str) if qty_str else 0.0
            avg_price = float(avg_price_str) if avg_price_str else 0.0
            cur_price = float(cur_price_str) if cur_price_str else avg_price
        except ValueError:
            continue

        # Create or get account before cash handling, so cash-only accounts
        # such as CMA accounts are included in the account map.
        account_key = account_name

        if account_key not in accounts:
            accounts[account_key] = {
                "name": account_name,
            }

        # Handle cash holdings (예수금)
        if '예수금' in ticker or '예수금' in stock_name:
            cash_holdings.append({
                "account_name": account_name,
                "account_key": account_key,
                "amount": qty,
                "currency": currency
            })
            continue

        # Skip zero quantity holdings
        if qty <= 0:
            continue

        # Add asset info (keyed by ticker code)
        if ticker not in asset_info:
            market = "US" if currency == "USD" else "KR"
            asset_info[ticker] = {
                "name": stock_name if stock_name else ticker,
                "market": market,
                "asset_type": "Stock",
                "currency": currency
            }

        # Add holding with name and current_price fields
        holdings.append({
            "account_key": account_key,
            "ticker": ticker,
            "name": stock_name if stock_name else ticker,
            "qty": qty,
            "avg_price": avg_price,
            "cur_price": cur_price
        })

    return {
        "holdings": holdings,
        "accounts": accounts,
        "asset_info": asset_info,
        "cash_holdings": cash_holdings
    }
