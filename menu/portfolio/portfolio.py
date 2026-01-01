"""
This module handles portfolio data management by integrating Google Sheets data
with KIS API data, maintaining a unified portfolio.json file.
"""
import gspread
from google.oauth2.service_account import Credentials
import json
import os
import logging
import threading
from datetime import datetime, timezone
import openpyxl
from openpyxl.styles import Font, Alignment
import display
try:
    from calculate_weights import calculate_target_weights, load_config
except ImportError:
    # Fallback/Placeholder if file not found during dev
    def calculate_target_weights(c, cfg, v=None): return {}, 0
    def load_config(p): return {}

import unicodedata

SERVICE_ACCOUNT_FILE = 'C:\\Users\\Lara\\steven\\service-account.json'
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]
SPREADSHEET_NAME = 'financial portfolio'
PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), 'portfolio.json')

# Owner definitions
OWNERS = [
    {"id": "owner_01", "name": "곽성훈"},
    {"id": "owner_02", "name": "염인선"}
]

def _get_owner_id(account_name: str) -> str:
    """Determine owner ID based on account name."""
    return "owner_02" if "인선" in account_name else "owner_01"

def _normalize_account_name(raw_name: str) -> str:
    """Create normalized account name for unique identification."""
    return raw_name.strip()

def _connect_google_sheet(sheet_name: str):
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

def _parse_worksheet_data(worksheet, currency: str) -> dict:
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
        account_name = row[5].strip() if len(row) > 5 else ""  # Col F: account
        cur_price_str = row[6].strip().replace(',', '').replace('$', '').replace('₩', '').replace('\\', '') if len(row) > 6 else ""  # Col G: current_price

        # Skip empty rows
        if not ticker or not account_name:
            continue

        # Parse quantity and prices
        try:
            qty = float(qty_str) if qty_str else 0.0
            avg_price = float(avg_price_str) if avg_price_str else 0.0
            cur_price = float(cur_price_str) if cur_price_str else avg_price
        except ValueError:
            continue

        # Handle cash holdings (예수금)
        if '예수금' in ticker or '예수금' in stock_name:
            cash_holdings.append({
                "account_name": account_name,
                "amount": qty,
                "currency": currency
            })
            continue

        # Create or get account
        owner_id = _get_owner_id(account_name)
        account_key = f"{account_name}_{owner_id}"

        if account_key not in accounts:
            accounts[account_key] = {
                "name": account_name,
                "owner_id": owner_id
            }

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


def _fetch_from_gsheet() -> dict:
    """
    Fetch portfolio data from Google Sheets (USD and KRW worksheets).

    Returns:
        dict: Portfolio data in the standard format
    """
    # Connect to worksheets
    usd_sheet = _connect_google_sheet('USD')
    krw_sheet = _connect_google_sheet('KRW')

    if not usd_sheet or not krw_sheet:
        return {"error": "Failed to connect to Google Sheets"}

    # Parse data from both sheets
    usd_data = _parse_worksheet_data(usd_sheet, "USD")
    krw_data = _parse_worksheet_data(krw_sheet, "KRW")

    # Merge accounts and assign IDs
    all_accounts = {}
    all_accounts.update(usd_data["accounts"])
    all_accounts.update(krw_data["accounts"])

    account_list = []
    account_id_map = {}
    for idx, (key, acc) in enumerate(all_accounts.items(), start=1):
        acc_id = f"acc_{idx:02d}"
        account_id_map[key] = acc_id
        account_list.append({
            "id": acc_id,
            "owner_id": acc["owner_id"],
            "name": acc["name"]
        })

    # Merge asset info
    all_asset_info = {}
    all_asset_info.update(usd_data["asset_info"])
    all_asset_info.update(krw_data["asset_info"])

    # Merge holdings with account IDs
    all_holdings = []
    for h in usd_data["holdings"] + krw_data["holdings"]:
        acc_id = account_id_map.get(h["account_key"], "unknown")
        all_holdings.append({
            "account_id": acc_id,
            "ticker": h["ticker"],
            "qty": h["qty"],
            "avg_price": h["avg_price"]
        })

    # Build portfolio structure
    portfolio = {
        "metadata": {
            "last_updated": datetime.now(timezone.utc).isoformat()
        },
        "owners": OWNERS,
        "asset_info": all_asset_info,
        "accounts": account_list,
        "holdings": all_holdings,
        "cash_holdings": usd_data["cash_holdings"] + krw_data["cash_holdings"]
    }

    return portfolio


def _convert_kis_to_portfolio(kis_data: dict) -> dict:
    """
    Convert KIS API data to portfolio format.

    Args:
        kis_data: Output from fetch_account_data()

    Returns:
        dict with 'holdings', 'accounts', 'asset_info', 'cash_holdings'
    """
    holdings = []
    accounts = {}
    asset_info = {}
    cash_holdings = []

    # KIS account (한국투자증권)
    kis_account_key = "한국투자증권_owner_01"
    accounts[kis_account_key] = {
        "name": "한국투자증권",
        "owner_id": "owner_01"
    }

    # Process domestic stocks (KR)
    for stock in kis_data.get('domestic_stocks', []):
        ticker = stock.get('ticker', '') or stock.get('symbol', '')
        qty = float(stock.get('qty', 0))
        avg_price = float(stock.get('avg_price', 0))
        name = stock.get('name', ticker)

        if qty <= 0:
            continue

        if ticker not in asset_info:
            asset_info[ticker] = {
                "name": name,
                "market": "KR",
                "asset_type": "Stock",
                "currency": "KRW"
            }

        holdings.append({
            "account_key": kis_account_key,
            "ticker": ticker,
            "name": name,
            "qty": qty,
            "avg_price": avg_price,
            "cur_price": float(stock.get('cur_price', 0))  # Include current price from KIS
        })

    # Process overseas stocks (US)
    for stock in kis_data.get('overseas_stocks', []):
        ticker = stock.get('symbol', '') or stock.get('ticker', '')
        qty = float(stock.get('qty', 0))
        avg_price = float(stock.get('avg_price', 0))
        name = stock.get('name', ticker)

        if qty <= 0:
            continue

        if ticker not in asset_info:
            asset_info[ticker] = {
                "name": name,
                "market": "US",
                "asset_type": "Stock",
                "currency": "USD"
            }

        holdings.append({
            "account_key": kis_account_key,
            "ticker": ticker,
            "name": name,
            "qty": qty,
            "avg_price": avg_price,
            "cur_price": float(stock.get('cur_price', 0))  # Include current price from KIS
        })

    # Add KRW orderable cash
    krw_orderable = kis_data.get('krw_orderable', 0)
    if krw_orderable:
        cash_holdings.append({
            "account_name": "한국투자증권",
            "amount": float(krw_orderable),
            "currency": "KRW"
        })

    # Add USD orderable cash
    overseas_asset = kis_data.get('overseas_asset', {})
    usd_orderable = float(overseas_asset.get('frcr_drwg_psbl_amt_1', 0))
    if usd_orderable > 0:
        cash_holdings.append({
            "account_name": "한국투자증권",
            "amount": usd_orderable,
            "currency": "USD"
        })

    return {
        "holdings": holdings,
        "accounts": accounts,
        "asset_info": asset_info,
        "cash_holdings": cash_holdings
    }


def _update_portfolio() -> tuple:
    """
    Update portfolio.json file by merging KIS API and GSheet data.

    Process Flow:
    1. _fetch_account_data() - KIS API data load
    2. _fetch_from_gsheet() - GSheet data load
    3. Merge data and remove duplicates
    4. Save to portfolio.json

    Returns:
        tuple: (success: bool, kis_data: dict or None)
    """
    from menu.handle_account_info import fetch_account_data
    from display import add_alert

    # Step 1: Fetch KIS API data
    add_alert("Fetching KIS API data...", "INFO")

    kis_portfolio = None
    kis_raw_data = None
    try:
        kis_raw_data = fetch_account_data()
        if kis_raw_data and not kis_raw_data.get('error'):
            kis_portfolio = _convert_kis_to_portfolio(kis_raw_data)
            kis_count = len(kis_portfolio.get('holdings', []))
            add_alert(f"KIS: {kis_count} holdings loaded", "SUCCESS")
        else:
            add_alert("KIS: No data or error", "WARN")
    except Exception as e:
        add_alert(f"KIS skipped: {str(e)[:30]}", "WARN")


    # Step 2: Fetch GSheet data
    add_alert("Fetching GSheet data...", "INFO")

    gsheet_data = _fetch_from_gsheet()

    if "error" in gsheet_data:
        add_alert(f"GSheet error: {gsheet_data['error']}", "ERROR")
        if not kis_portfolio:
            return False, kis_raw_data
        # Use only KIS data if GSheet fails
        gsheet_data = {"accounts": {}, "holdings": [], "asset_info": {}, "cash_holdings": []}

    # Step 3: Merge data

    # Merge accounts
    all_accounts = {}
    if kis_portfolio:
        all_accounts.update(kis_portfolio["accounts"])
    # GSheet accounts come from _fetch_from_gsheet which already has account_list format
    # We need to rebuild from the raw data

    # For GSheet, we need to get the raw accounts before they were converted to list
    usd_sheet = _connect_google_sheet('USD')
    krw_sheet = _connect_google_sheet('KRW')

    gsheet_accounts = {}
    gsheet_holdings = []
    gsheet_asset_info = {}
    gsheet_cash = []

    if usd_sheet:
        usd_data = _parse_worksheet_data(usd_sheet, "USD")
        gsheet_accounts.update(usd_data["accounts"])
        gsheet_holdings.extend(usd_data["holdings"])
        gsheet_asset_info.update(usd_data["asset_info"])
        gsheet_cash.extend(usd_data["cash_holdings"])

    if krw_sheet:
        krw_data = _parse_worksheet_data(krw_sheet, "KRW")
        gsheet_accounts.update(krw_data["accounts"])
        gsheet_holdings.extend(krw_data["holdings"])
        gsheet_asset_info.update(krw_data["asset_info"])
        gsheet_cash.extend(krw_data["cash_holdings"])

    all_accounts.update(gsheet_accounts)

    # Assign account IDs
    account_list = []
    account_id_map = {}
    for idx, (key, acc) in enumerate(all_accounts.items(), start=1):
        acc_id = f"acc_{idx:02d}"
        account_id_map[key] = acc_id
        account_list.append({
            "id": acc_id,
            "owner_id": acc["owner_id"],
            "name": acc["name"]
        })

    # Merge asset info
    all_asset_info = {}
    if kis_portfolio:
        all_asset_info.update(kis_portfolio["asset_info"])
    all_asset_info.update(gsheet_asset_info)

    # Merge holdings with account IDs, name, and cur_price fields
    all_holdings = []
    if kis_portfolio:
        for h in kis_portfolio["holdings"]:
            acc_id = account_id_map.get(h["account_key"], "unknown")
            all_holdings.append({
                "account_id": acc_id,
                "ticker": h["ticker"],
                "name": h.get("name", h["ticker"]),
                "qty": h["qty"],
                "avg_price": h["avg_price"],
                "cur_price": h.get("cur_price", h["avg_price"])
            })

    for h in gsheet_holdings:
        acc_id = account_id_map.get(h["account_key"], "unknown")
        all_holdings.append({
            "account_id": acc_id,
            "ticker": h["ticker"],
            "name": h.get("name", h["ticker"]),
            "qty": h["qty"],
            "avg_price": h["avg_price"],
            "cur_price": h.get("cur_price", h["avg_price"])
        })

    # Merge cash holdings
    all_cash = []
    if kis_portfolio:
        all_cash.extend(kis_portfolio["cash_holdings"])
    all_cash.extend(gsheet_cash)

    # Build final portfolio
    portfolio = {
        "metadata": {
            "last_updated": datetime.now(timezone.utc).isoformat()
        },
        "owners": OWNERS,
        "asset_info": all_asset_info,
        "accounts": account_list,
        "holdings": all_holdings,
        "cash_holdings": all_cash
    }

    # Step 4: Save to portfolio.json
    try:
        with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
            json.dump(portfolio, f, ensure_ascii=False, indent=2)
        return True, kis_raw_data
    except Exception as e:
        notify(f"Failed to save portfolio: {e}", "ERROR")
        return False, kis_raw_data


def _load_portfolio() -> dict:
    """Load portfolio data from portfolio.json."""
    try:
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}


def _calculate_portfolio_stats(exchange_rate: float, current_prices: dict = None) -> dict:
    """
    Calculate portfolio statistics with USD/KRW breakdown.
    Uses current prices if provided, otherwise falls back to avg_price.

    Args:
        exchange_rate: KRW/USD exchange rate
        current_prices: dict of {ticker: current_price}

    Returns:
        dict with us_stock_usd, us_cash_usd, kr_stock_krw, kr_cash_krw, etc.
    """
    portfolio = _load_portfolio()
    if "error" in portfolio:
        return {"error": portfolio["error"]}

    if current_prices is None:
        current_prices = {}

    # Initialize totals
    us_stock_usd = 0.0
    us_cash_usd = 0.0
    kr_stock_krw = 0.0
    kr_cash_krw = 0.0

    # Calculate stock values using current prices (fall back to avg if not available)
    asset_info = portfolio.get("asset_info", {})
    holdings = portfolio.get("holdings", [])

    for h in holdings:
        ticker = h.get("ticker", "")
        qty = h.get("qty", 0)
        avg_price = h.get("avg_price", 0)
        # Priority: holding's cur_price > external current_prices > avg_price
        cur_price = h.get("cur_price", current_prices.get(ticker, avg_price))
        value = qty * cur_price

        # Determine currency from asset_info
        info = asset_info.get(ticker, {})
        currency = info.get("currency", "USD")

        if currency == "USD":
            us_stock_usd += value
        else:
            kr_stock_krw += value

    # Calculate cash holdings
    cash_holdings = portfolio.get("cash_holdings", [])
    for c in cash_holdings:
        amount = c.get("amount", 0)
        currency = c.get("currency", "USD")
        if currency == "USD":
            us_cash_usd += amount
        else:
            kr_cash_krw += amount

    # Convert with exchange rate
    us_stock_krw = us_stock_usd * exchange_rate
    us_cash_krw = us_cash_usd * exchange_rate
    kr_stock_usd = kr_stock_krw / exchange_rate if exchange_rate > 0 else 0
    kr_cash_usd = kr_cash_krw / exchange_rate if exchange_rate > 0 else 0

    # Calculate totals
    total_usd = us_stock_usd + us_cash_usd + kr_stock_usd + kr_cash_usd
    total_krw = us_stock_krw + us_cash_krw + kr_stock_krw + kr_cash_krw

    # Percentages - based on USD total
    us_pct = ((us_stock_usd + us_cash_usd) / total_usd * 100) if total_usd > 0 else 0
    kr_pct = ((kr_stock_usd + kr_cash_usd) / total_usd * 100) if total_usd > 0 else 0

    # Cash ratios within each currency's total assets
    us_total_assets = us_stock_usd + us_cash_usd
    kr_total_assets = kr_stock_krw + kr_cash_krw
    us_cash_ratio = (us_cash_usd / us_total_assets * 100) if us_total_assets > 0 else 0
    kr_cash_ratio = (kr_cash_krw / kr_total_assets * 100) if kr_total_assets > 0 else 0

    return {
        "us_stock_usd": us_stock_usd,
        "us_cash_usd": us_cash_usd,
        "us_stock_krw": us_stock_krw,
        "us_cash_krw": us_cash_krw,
        "kr_stock_usd": kr_stock_usd,
        "kr_cash_usd": kr_cash_usd,
        "kr_stock_krw": kr_stock_krw,
        "kr_cash_krw": kr_cash_krw,
        "total_stock_usd": us_stock_usd + kr_stock_usd,
        "total_cash_usd": us_cash_usd + kr_cash_usd,
        "total_stock_krw": us_stock_krw + kr_stock_krw,
        "total_cash_krw": us_cash_krw + kr_cash_krw,
        "us_pct": us_pct,
        "kr_pct": kr_pct,
        "us_cash_ratio": us_cash_ratio,
        "kr_cash_ratio": kr_cash_ratio
    }


def _format_currency(value: float, currency: str, short: bool = False) -> str:
    """Format currency value with proper symbol and abbreviation."""
    if currency == "USD":
        if short and abs(value) >= 1000:
            return f"$ {value/1000:,.1f}K"
        return f"$ {value:,.2f}"
    else:
        if short and abs(value) >= 1000000:
            return f"₩ {value/1000000:,.1f}M"
        elif short and abs(value) >= 1000:
            return f"₩ {value/1000:,.0f}K"
        return f"₩ {value:,.0f}"



def _get_merged_portfolio_stat(current_prices: dict = None, exchange_rate: float = 1435.0):
    """
    Load portfolio, merge holdings by ticker, and calculate total value.
    Returns:
        (merged_dict, total_value_usd)

    merged_dict format:
    {
        ticker: {
            "qty", "total_investment_krw", "cur_price", "name", "currency",
            "current_value_usd", "current_value_krw", ...
        }
    }
    """
    portfolio = _load_portfolio()
    if "error" in portfolio:
        return {}, 0.0

    if current_prices is None:
        current_prices = {}

    asset_info = portfolio.get("asset_info", {})
    holdings = portfolio.get("holdings", [])
    cash_holdings = portfolio.get("cash_holdings", [])

    merged = {}
    total_val_usd = 0.0

    # 1. Process Stocks
    for h in holdings:
        ticker = h.get("ticker", "")
        qty = h.get("qty", 0)
        avg_price = h.get("avg_price", 0)
        cur_price = h.get("cur_price", current_prices.get(ticker, avg_price))
        info = asset_info.get(ticker, {})
        name = h.get("name", info.get("name", ticker))
        currency = info.get("currency", "USD")

        if ticker not in merged:
            merged[ticker] = {
                "qty": 0.0,
                "total_investment": 0.0,
                "cur_price": cur_price,
                "name": name,
                "currency": currency,
                "type": "STOCK"
            }

        # Aggregate
        merged[ticker]["qty"] += qty
        merged[ticker]["total_investment"] += qty * avg_price
        if cur_price > 0:
            merged[ticker]["cur_price"] = cur_price

    # 2. Process Cash (USD/KRW) - Create as pseudo-tickers for weight calc
    usd_cash = sum(c["amount"] for c in cash_holdings if c.get("currency") == "USD")
    krw_cash = sum(c["amount"] for c in cash_holdings if c.get("currency") == "KRW")

    if usd_cash > 0:
        merged["USD cash"] = {
            "qty": usd_cash, "total_investment": usd_cash, "cur_price": 1.0,
            "name": "USD cash", "currency": "USD", "type": "CASH"
        }

    if krw_cash > 0:
        merged["KRW cash"] = {
            "qty": krw_cash, "total_investment": krw_cash, "cur_price": 1.0,
            "name": "KRW cash", "currency": "KRW", "type": "CASH"
        }

    # 3. Calculate Values & Total
    for ticker, data in merged.items():
        qty = data["qty"]
        cur_price = data["cur_price"]
        currency = data["currency"]

        # Value in native currency
        val_native = qty * cur_price
        data["current_value_native"] = val_native

        # Convert to USD for uniform weight calculation
        if currency == "USD":
            val_usd = val_native
            val_krw = val_native * exchange_rate
        else:
            val_krw = val_native
            val_usd = val_native / exchange_rate if exchange_rate > 0 else 0

        data["current_value_usd"] = val_usd
        data["current_value_krw"] = val_krw

        total_val_usd += val_usd

    return merged, total_val_usd

def calc_weight_diffs(merged_data, current_weights, targets,
                       total_value_usd: float, exchange_rate: float) -> list:
    """
    Calculate weight differences between current and target allocations.

    Args:
        merged_data: Merged holdings data by ticker
        current_weights: Current weight per ticker
        targets: Target weight per ticker
        total_value_usd: Total portfolio value in USD
        exchange_rate: KRW/USD exchange rate

    Returns:
        list: Sorted list of diffs (by abs_diff descending), each containing:
            ticker, name, cur_w, tgt_w, diff, abs_diff, qty_diff
    """
    diffs = []

    # We care about all tickers in either Targets OR Current
    all_tickers = set(current_weights.keys()) | set(targets.keys())

    for t in all_tickers:
        cur_w = current_weights.get(t, 0.0)
        tgt_w = targets.get(t, 0.0)

        # Filter Cash
        data = merged_data.get(t, {})
        if data.get("type") == "CASH" or "cash" in t.lower() or "예수금" in t:
            continue

        diff = tgt_w - cur_w  # Target - Current
        name = data.get("name", t)

        # Calculate quantity diff
        val_diff_usd = diff * total_value_usd
        cur_price = data.get("cur_price", 0)
        currency = data.get("currency", "USD")

        qty_diff = 0
        if cur_price > 0:
            if currency == "KRW":
                val_diff_krw = val_diff_usd * exchange_rate
                qty_diff = val_diff_krw / cur_price
            else:
                qty_diff = val_diff_usd / cur_price

        diffs.append({
            "ticker": t,
            "name": name,
            "cur_w": cur_w,
            "tgt_w": tgt_w,
            "diff": diff,
            "abs_diff": abs(diff),
            "qty_diff": int(qty_diff)
        })

    # Sort by absolute difference descending
    diffs.sort(key=lambda x: x["abs_diff"], reverse=True)

    return diffs


def _check_portfolio_balance(merged_data, total_value_usd, current_weights, targets, exchange_rate):
    """
    Display weight differences with pagination UI.
    """
    from display import show_in_result_area, get_fixed_width_name, input_at

    if total_value_usd <= 0:
        display.add_alert("Total asset value is 0 or error.", "ERROR")
        return

    # Calculate diffs
    diffs = calc_weight_diffs(merged_data, current_weights, targets,
                               total_value_usd, exchange_rate)

    # Pagination
    import math
    page = 0
    page_size = 6
    total_pages = math.ceil(len(diffs) / page_size)
    if total_pages == 0: total_pages = 1

    while True:
        # Slice for current page
        start_idx = page * page_size
        end_idx = start_idx + page_size
        page_items = diffs[start_idx:end_idx]

        lines = []
        lines.append(f" [Portfolio Check] (Total: ${total_value_usd:,.0f}) - Page {page+1}/{total_pages}")

        # Header
        header = f" {'#':>2} | {'Ticker':<10} | {'Name':<30} | {'Curr %':>8} | {'Tgt %':>8} | {'Diff %':>9} | {'Qty':>6}"
        sep_len = len(header)

        lines.append("─" * sep_len)
        lines.append(header)
        lines.append("─" * sep_len)

        for i, item in enumerate(page_items):
            global_idx = start_idx + i + 1
            t = item["ticker"]

            # Truncate/Pad name for display (width 30)
            n = get_fixed_width_name(item['name'], 30)
            c_p = item["cur_w"] * 100
            t_p = item["tgt_w"] * 100
            d_p = item["diff"] * 100
            qty_diff = item["qty_diff"]

            # Qty string (int)
            qty_str = f"{int(qty_diff):+d}"

            # Colorize Diff (Positive = Buy = Green, Negative = Sell = Red)
            from display import COLOR_RED, COLOR_GREEN, COLOR_RESET
            symbol = "+" if d_p >= 0 else "-"

            c_str = f"{c_p:4.2f}%"
            t_str = f"{t_p:4.2f}%"
            base_d_str = f"{symbol}{abs(d_p):5.2f}%"

            # Color Logic
            if d_p > 0.5:
                colored_d_str = f"{COLOR_GREEN}{base_d_str}{COLOR_RESET}"
                colored_qt_str = f"{COLOR_GREEN}{qty_str:>6}{COLOR_RESET}"
            elif d_p < -0.5:
                colored_d_str = f"{COLOR_RED}{base_d_str}{COLOR_RESET}"
                colored_qt_str = f"{COLOR_RED}{qty_str:>6}{COLOR_RESET}"
            else:
                colored_d_str = base_d_str
                colored_qt_str = f"{qty_str:>6}"

            # Alignment padding for width 9 for Diff %
            target_width = 9
            padding = " " * (target_width - len(base_d_str))
            final_d_str = padding + colored_d_str

            lines.append(f" {global_idx:>2} | {t:<10} | {n} | {c_str:>8} | {t_str:>8} | {final_d_str} | {colored_qt_str}")

        remaining_lines = page_size - len(page_items)
        for _ in range(remaining_lines):
            lines.append("")  # Empty lines to keep UI stable

        lines.append("─" * sep_len)
        lines.append(" (Enter: Next Page, q: Return)")

        show_in_result_area(lines)

        # Input Loop
        cmd = input_at(13, 2, "Cmd (Ent/q): ").strip().lower()
        if cmd == 'q':
            break
        else:
            page = (page + 1) % total_pages


def _export_portfolio_excel(merged_data, current_weights, targets) -> bool:
    """
    Export portfolio to Excel (.xlsx) with formatted columns.
    Requires 'openpyxl' library.
    """
    from display import add_alert
    try:
        import openpyxl
        from openpyxl.styles import Font, Alignment
    except ImportError:
        add_alert("openpyxl not found. Please install: pip install openpyxl", "ERROR")
        return False

    from datetime import datetime
    import os

    rows = []

    for ticker, data in merged_data.items():
        qty = data["qty"]
        if qty <= 0: continue

        cur_price = data["cur_price"]
        total_inv = data["total_investment"]
        cur_val = data["current_value_native"]

        avg_price = total_inv / qty if qty > 0 else 0
        change = cur_val - total_inv
        # Return pct for Excel: Ratio (0.20 = 20%)
        ret_pct = (change / total_inv) if total_inv > 0 else 0

        currency = data["currency"]

        # Weigths
        cur_w = current_weights.get(ticker, 0.0)
        tgt_w = targets.get(ticker, 0.0)

        # Sort key logic
        sort_idx = 0 if currency == "USD" else 1
        if data.get("type") == "CASH": sort_idx += 2

        rows.append({
            "ticker": ticker,
            "name": data["name"],
            "cur_w": cur_w,
            "tgt_w": tgt_w,
            "qty": qty,
            "avg_price": avg_price,
            "cur_price": cur_price,
            "total_inv": total_inv,
            "cur_val": cur_val,
            "change": change,
            "ret_pct": ret_pct,
            "sort_key": (sort_idx, ticker)
        })

    # Sort
    rows.sort(key=lambda x: x["sort_key"])

    # Create Workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Portfolio"

    # Headers
    headers = ["Ticker", "Name", "Cur Wgt", "Tgt Wgt", "Qty", "Avg Price", "Cur Price", "Invest", "Cur Val", "Change", "Ret %"]
    ws.append(headers)

    # Style Headers: Bold + Center
    header_font = Font(bold=True)
    header_align = Alignment(horizontal="center")
    for cell in ws[1]:
        cell.font = header_font
        cell.alignment = header_align

    # Write Data
    for r in rows:
        ws.append([
            r["ticker"], r["name"], r["cur_w"], r["tgt_w"], r["qty"],
            r["avg_price"], r["cur_price"], r["total_inv"], r["cur_val"],
            r["change"], r["ret_pct"]
        ])

    # Formatting
    # Columns (1-based):
    # A(1):Ticker, B(2):Name, C(3):CurW, D(4):TgtW, E(5):Qty
    # F(6):Avg, G(7):CurP, H(8):Inv, I(9):Val, J(10):Chg, K(11):Ret%

    number_fmt = "#,##0.00"
    pct_fmt = "0.00%"

    for row_idx in range(2, len(rows) + 2):
        # Weights (C, D)
        ws.cell(row=row_idx, column=3).number_format = pct_fmt
        ws.cell(row=row_idx, column=4).number_format = pct_fmt

        # Qty (E)
        ws.cell(row=row_idx, column=5).number_format = "#,##0.00"

        # Prices/Values (F-J)
        for col_idx in range(6, 11):
            ws.cell(row=row_idx, column=col_idx).number_format = number_fmt

        # Return (K)
        ws.cell(row=row_idx, column=11).number_format = pct_fmt

    # Column Widths
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 35
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 10
    ws.column_dimensions['E'].width = 10
    ws.column_dimensions['F'].width = 14
    ws.column_dimensions['G'].width = 14
    ws.column_dimensions['H'].width = 16
    ws.column_dimensions['I'].width = 16
    ws.column_dimensions['J'].width = 16
    ws.column_dimensions['K'].width = 10

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"portfolio_export_{timestamp}.xlsx"
    filepath = os.path.join(os.path.dirname(__file__), filename)

    try:
        wb.save(filepath)
        add_alert(f"Excel exported: {filename}", "SUCCESS")
        return True
    except Exception as e:
        add_alert(f"Excel save failed: {e}", "ERROR")
        return False


def get_portfolio() -> dict:
    """
    Fetch and calculate portfolio data.
    Syncs portfolio.json and calculates weights/targets.

    Args:
        silent (bool): If True, suppress UI refreshes and use thread-safe alerts.

    Returns:
        dict: {
            "merged_data": dict,      # Merged holdings by ticker
            "total_value_usd": float, # Total portfolio value in USD
            "current_weights": dict,  # Current weight per ticker
            "targets": dict,          # Target weight per ticker
            "stats": dict,            # Summary stats (us_stock_usd, etc.)
            "exchange_rate": float,   # KRW/USD exchange rate
            "error": str or None      # Error message if any
        }
    """
    from display import add_alert

    result = {
        "merged_data": {},
        "total_value_usd": 0.0,
        "current_weights": {},
        "targets": {},
        "stats": {},
        "exchange_rate": 1435.0,
        "error": None
    }

    # Sync portfolio data and get KIS data
    success, kis_data = _update_portfolio()

    # If _update_portfolio failed but we have locally cached data,
    # we might still want to proceed for display purposes if possible.
    # But usually _update_portfolio handles the sync logic.

    exchange_rate = 1435.0
    current_prices = {}

    # Extract current prices from KIS data
    if kis_data and not kis_data.get('error'):
        exchange_rate = kis_data.get('exchange_rate', 1435.0)
        for stock in kis_data.get('domestic_stocks', []):
            symbol = stock.get('symbol', '')
            if symbol:
                current_prices[symbol] = stock.get('cur_price', 0)
        for stock in kis_data.get('overseas_stocks', []):
            symbol = stock.get('symbol', '')
            if symbol:
                current_prices[symbol] = stock.get('cur_price', 0)

        add_alert(f"Loaded {len(current_prices)} prices", "SUCCESS")

    result["exchange_rate"] = exchange_rate

    # Calculate stats
    stats = _calculate_portfolio_stats(exchange_rate, current_prices)
    if "error" in stats:
        result["error"] = stats["error"]
        return result
    result["stats"] = stats

    # Get merged data
    merged_data, total_value_usd = _get_merged_portfolio_stat(current_prices, exchange_rate)
    result["merged_data"] = merged_data
    result["total_value_usd"] = total_value_usd

    # Calculate current weights
    current_weights = {}
    if total_value_usd > 0:
        for ticker, data in merged_data.items():
            current_weights[ticker] = data["current_value_usd"] / total_value_usd
    result["current_weights"] = current_weights

    # Calculate target weights
    targets = {}
    try:
        config_path = os.path.join(os.path.dirname(__file__), "portfolio_weights.json")
        if not os.path.exists(config_path):
            config_path = "portfolio_weights.json"
        config = load_config(config_path)
        targets, score = calculate_target_weights(current_weights, config)
    except Exception as e:
        add_alert(f"Weight calc error: {e}", "ERROR")
    result["targets"] = targets
    result["price_map"] = current_prices

    return result


def portfolio_menu():
    """
    Portfolio menu interface using modular get_portfolio() function.
    Displays summary and handles menu interactions.
    """
    from display import show_in_result_area, input_at, render_ui, clear_result_area, process_pending_alerts

    # Get portfolio data
    portfolio_data = get_portfolio()

    if portfolio_data.get("error"):
        display.add_alert(f"Portfolio error: {portfolio_data['error']}", "ERROR")
        return

    # Extract data
    merged_data = portfolio_data["merged_data"]
    total_value_usd = portfolio_data["total_value_usd"]
    current_weights = portfolio_data["current_weights"]
    targets = portfolio_data["targets"]
    stats = portfolio_data["stats"]
    exchange_rate = portfolio_data["exchange_rate"]


    while True:
        process_pending_alerts()
        clear_result_area()

        # Build summary lines
        lines = []
        lines.append(f" [Portfolio] (Rate: {exchange_rate:,.2f} KRW/USD) (Total: ${total_value_usd:,.0f})")
        lines.append("─" * 80)
        lines.append(f" {'':10} │ {'USD':^27} │ {'KRW':^27} │ {'%':^6}")
        lines.append("─" * 80)

        def _align_pair(val1, val2, curr1, curr2, width=6):
            """Format and align two currency values for a table cell."""
            sym1 = "$ " if curr1 == "USD" else "₩ "
            sym2 = "$ " if curr2 == "USD" else "₩ "

            def _get_num(v, c):
                if c == "USD":
                    return f"{v/1000:,.1f}K" if abs(v) >= 1000 else f"{v:,.2f}"
                else:
                    if abs(v) >= 1000000: return f"{v/1000000:,.1f}M"
                    return f"{v/1000:,.0f}K" if abs(v) >= 1000 else f"{v:,.0f}"

            s1 = f"{sym1}{_get_num(val1, curr1).rjust(width)}"
            s2 = f"{sym2}{_get_num(val2, curr2).rjust(width)}"
            return f"{s1} / {s2}"

        # US Assets row
        us_usd = _align_pair(stats['us_stock_usd'], stats['us_cash_usd'], "USD", "USD")
        us_krw = _align_pair(stats['us_stock_krw'], stats['us_cash_krw'], "KRW", "KRW")
        lines.append(f" {'US Assets':10} │ {us_usd:^27} │ {us_krw:^27} │ {stats['us_pct']:5.1f}%")

        # KR Assets row
        kr_usd = _align_pair(stats['kr_stock_usd'], stats['kr_cash_usd'], "USD", "USD")
        kr_krw = _align_pair(stats['kr_stock_krw'], stats['kr_cash_krw'], "KRW", "KRW")
        lines.append(f" {'KR Assets':10} │ {kr_usd:^27} │ {kr_krw:^27} │ {stats['kr_pct']:5.1f}%")

        lines.append("─" * 80)

        # Total row
        tot_usd = _align_pair(stats['total_stock_usd'], stats['total_cash_usd'], "USD", "USD")
        tot_krw = _align_pair(stats['total_stock_krw'], stats['total_cash_krw'], "KRW", "KRW")
        lines.append(f" {'Total':10} │ {tot_usd:^27} │ {tot_krw:^27} │")

        # Cash ratio row
        us_cash_str = f"{stats['us_cash_ratio']:>14.1f}        %"
        kr_cash_str = f"{stats['kr_cash_ratio']:>14.1f}        %"
        lines.append(f" {'Cash':10} │ {us_cash_str:27} │ {kr_cash_str:27} │")
        lines.append("─" * 80)
        lines.append(" 1. Check Portfolio  2. Excel Export  3. Value Averaging  q. Exit")

        show_in_result_area(lines)

        choice = input_at(13, 2, "Enter Choice: ").strip().lower()

        if choice == '1':
            _check_portfolio_balance(merged_data, total_value_usd, current_weights, targets, exchange_rate)
            input_at(13, 2, "Press Enter to continue...")
        elif choice == '2':
            _export_portfolio_excel(merged_data, current_weights, targets)
            input_at(13, 2, "Press Enter to continue...")
        elif choice == '3':
             from . import value_averaging
             from menu.handle_account_info import fetch_price
             from display import show_in_result_area, input_at

             va_config = value_averaging.load_config()
             target_ticker = va_config.get('target', '')
             target_weight = 0.0

             if target_ticker:
                 target_weight = targets.get(target_ticker, 0.0)

             # Get price from price_map or fetch if missing
             price_map = portfolio_data.get("price_map", {})
             current_price_override = price_map.get(target_ticker, 0.0)

             if current_price_override == 0:
                  print(f" [Info] Price for {target_ticker} not found in portfolio. Fetching from API...")
                  try:
                      current_price_override = fetch_price(target_ticker)
                  except Exception as e:
                      print(f" [Warning] Failed to fetch price: {e}")

             # Execute Calculation with INJECTED data
             res = value_averaging.calculate_order(merged_data, total_value_usd, target_weight, current_price_override)

             # Build Display Lines
             lines = []

             # Header
             lines.append(f" [Value Averaging] {res.get('date')}")
             lines.append("="*50)

             if res.get("error"):
                 lines.append(f" ERROR: {res.get('error')}")
             else:
                 orders = res.get("orders", [])
                 t_w_pct = res.get("target_weight", 0) * 100
                 curr_p = res.get("current_price", 0)
                 daily_b = res.get("daily_budget", 0)
                 buy_amt = res.get("daily_target_amount", 0)

                 lines.append(f" Target Ticker   : {target_ticker}")
                 lines.append(f" Target Weight   : {t_w_pct:.2f}%")
                 lines.append(f" Current Price   : ${curr_p:,.2f}")
                 lines.append(f" Daily Budget    : ${daily_b:,.2f}")
                 lines.append("-" * 50)
                 lines.append(f" Total Buy Amount: ${buy_amt:,.2f}")
                 lines.append("-" * 50)

                 if curr_p == 0:
                     lines.append(" [WARNING] Current Price is $0.00.")
                     lines.append(" Cannot calculate buy qty. Check KIS API.")
                 else:
                     if orders:
                         lines.append(f" Orders Generated: {len(orders)}")
                         for o in orders:
                             lines.append(f"  > {o['type']} | {o['ticker']} | {o['qty']} qty | ${o['price']:.2f} (LOC)")
                     else:
                         lines.append(" No orders generated (Target met).")

             show_in_result_area(lines)

             # Execution Prompt
             if res.get("orders") and res.get("current_price", 0) > 0:
                 confirm = input_at(13, 2, " Execute Orders? (y/n): ").strip().lower()
                 if confirm == 'y':
                      exec_res = value_averaging.execute_orders(res)
                      lines.append("-" * 50)
                      lines.append(" Execution Result:")
                      for r in exec_res:
                          status = "SUCCESS" if r['success'] else "FAILED"
                          lines.append(f"  {status}: {r['message']}")
                      # Refresh display with results
                      show_in_result_area(lines)

             input_at(13, 2, " Press Enter to continue...")
        elif choice == 'q':
            break

    render_ui(full_refresh=True)


if __name__ == "__main__":
    # Quick test
    result = _update_portfolio()
    if result:
        print("Portfolio sync completed successfully!")
    else:
        print("Portfolio sync failed!")


