"""
This module handles portfolio data management by integrating Google Sheets data
with KIS API data, maintaining a unified portfolio.json file.
"""
import gspread
from google.oauth2.service_account import Credentials
import json
import os
from datetime import datetime, timezone
import display

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


def fetch_from_gsheet() -> dict:
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
            "avg_price": avg_price
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
            "avg_price": avg_price
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


def update_portfolio() -> bool:
    """
    Update portfolio.json file by merging KIS API and GSheet data.

    Process Flow:
    1. fetch_account_data() - KIS API data load
    2. fetch_from_gsheet() - GSheet data load
    3. Merge data and remove duplicates
    4. Save to portfolio.json

    Returns:
        bool: True if successful, False otherwise
    """
    from menu.handle_account_info import fetch_account_data
    from display import render_ui

    # Step 1: Fetch KIS API data
    display.add_alert("Fetching KIS API data...", "INFO")
    render_ui(full_refresh=True)
    kis_portfolio = None
    try:
        kis_data = fetch_account_data()
        if kis_data and not kis_data.get('error'):
            kis_portfolio = _convert_kis_to_portfolio(kis_data)
            kis_count = len(kis_portfolio.get('holdings', []))
            display.add_alert(f"KIS: {kis_count} holdings loaded", "SUCCESS")
        else:
            display.add_alert("KIS: No data or error", "WARN")
    except Exception as e:
        display.add_alert(f"KIS skipped: {str(e)[:30]}", "WARN")
    render_ui(full_refresh=True)

    # Step 2: Fetch GSheet data
    display.add_alert("Fetching GSheet data...", "INFO")
    render_ui(full_refresh=True)
    gsheet_data = fetch_from_gsheet()

    if "error" in gsheet_data:
        display.add_alert(f"GSheet error: {gsheet_data['error']}", "ERROR")
        if not kis_portfolio:
            return False
        # Use only KIS data if GSheet fails
        gsheet_data = {"accounts": {}, "holdings": [], "asset_info": {}, "cash_holdings": []}

    # Step 3: Merge data

    # Merge accounts
    all_accounts = {}
    if kis_portfolio:
        all_accounts.update(kis_portfolio["accounts"])
    # GSheet accounts come from fetch_from_gsheet which already has account_list format
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
        return True
    except Exception as e:
        display.add_alert(f"Failed to save portfolio: {e}", "ERROR")
        return False


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


def export_portfolio_csv(current_prices: dict = None) -> bool:
    """
    Export portfolio to CSV with merged tickers and sorted by currency.

    Merges same tickers across accounts (weighted average for avg_price).
    Sort order: US stocks, US cash, KR stocks, KR cash

    Columns: ticker, item_name, qty, avg_price, current_price, current_value, investment, change, return_pct
    """
    import csv

    portfolio = _load_portfolio()
    if "error" in portfolio:
        display.add_alert(f"Failed to load portfolio: {portfolio['error']}", "ERROR")
        return False

    if current_prices is None:
        current_prices = {}

    # Merge holdings by ticker
    merged = {}  # {ticker: {qty, total_investment, cur_price, name, currency}}

    asset_info = portfolio.get("asset_info", {})
    holdings = portfolio.get("holdings", [])

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
                "qty": 0,
                "total_investment": 0,
                "cur_price": cur_price,
                "name": name,
                "currency": currency
            }

        merged[ticker]["qty"] += qty
        merged[ticker]["total_investment"] += qty * avg_price
        # Use most recent cur_price (prefer non-zero)
        if cur_price > 0:
            merged[ticker]["cur_price"] = cur_price

    # Build rows with calculated fields
    rows = []
    for ticker, data in merged.items():
        qty = data["qty"]
        total_investment = data["total_investment"]
        avg_price = total_investment / qty if qty > 0 else 0
        cur_price = data["cur_price"] if data["cur_price"] > 0 else avg_price
        current_value = qty * cur_price
        change = current_value - total_investment
        return_pct = ((cur_price - avg_price) / avg_price * 100) if avg_price > 0 else 0

        rows.append({
            "ticker": ticker,
            "item_name": data["name"],
            "qty": round(qty, 2),
            "avg_price": round(avg_price, 2),
            "current_price": round(cur_price, 2),
            "current_value": round(current_value, 2),
            "investment": round(total_investment, 2),
            "change": round(change, 2),
            "return_pct": round(return_pct, 2),
            "currency": data["currency"]  # For sorting
        })

    # Sort: US stocks first, then KR stocks
    rows.sort(key=lambda x: (0 if x["currency"] == "USD" else 1, x["ticker"]))

    # Add cash holdings
    cash_holdings = portfolio.get("cash_holdings", [])

    # Merge cash by currency
    usd_cash = sum(c["amount"] for c in cash_holdings if c.get("currency") == "USD")
    krw_cash = sum(c["amount"] for c in cash_holdings if c.get("currency") == "KRW")

    # Add US cash after US stocks
    if usd_cash > 0:
        us_stock_count = len([r for r in rows if r["currency"] == "USD"])
        rows.insert(us_stock_count, {
            "ticker": "USD_CASH",
            "item_name": "US Dollar Cash",
            "qty": round(usd_cash, 2),
            "avg_price": 1,
            "current_price": 1,
            "current_value": round(usd_cash, 2),
            "investment": round(usd_cash, 2),
            "change": 0,
            "return_pct": 0,
            "currency": "USD"
        })

    # Add KR cash at the end
    if krw_cash > 0:
        rows.append({
            "ticker": "KRW_CASH",
            "item_name": "Korean Won Cash",
            "qty": round(krw_cash, 0),
            "avg_price": 1,
            "current_price": 1,
            "current_value": round(krw_cash, 0),
            "investment": round(krw_cash, 0),
            "change": 0,
            "return_pct": 0,
            "currency": "KRW"
        })

    # Remove currency field before writing (was only for sorting)
    for row in rows:
        del row["currency"]

    # Write CSV with timestamp in filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(os.path.dirname(__file__), f'portfolio_export_{timestamp}.csv')
    try:
        fieldnames = ["ticker", "item_name", "qty", "avg_price", "current_price", "investment", "current_value", "change", "return_pct"]
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        display.add_alert(f"CSV exported: {len(rows)} items", "SUCCESS")
        return True
    except Exception as e:
        display.add_alert(f"CSV export failed: {e}", "ERROR")
        return False


def show_portfolio_summary():
    """
    Display portfolio summary UI and handle menu interactions.
    Fetches KIS API data once at start and caches for reuse.
    """
    from display import show_in_result_area, input_at, render_ui, clear_result_area
    from menu.handle_account_info import fetch_account_data

    # First sync portfolio data
    display.add_alert("Syncing portfolio...", "INFO")
    render_ui(full_refresh=True)
    update_portfolio()

    # Fetch KIS API data once and cache
    display.add_alert("Loading current prices...", "INFO")
    render_ui(full_refresh=True)

    exchange_rate = 1435.0  # Default
    current_prices = {}

    try:
        kis_data = fetch_account_data()
        if kis_data and not kis_data.get('error'):
            exchange_rate = kis_data.get('exchange_rate', 1435.0)
            # Cache current prices from KIS data
            for stock in kis_data.get('domestic_stocks', []):
                symbol = stock.get('symbol', '')
                if symbol:
                    current_prices[symbol] = stock.get('cur_price', 0)
            for stock in kis_data.get('overseas_stocks', []):
                symbol = stock.get('symbol', '')
                if symbol:
                    current_prices[symbol] = stock.get('cur_price', 0)
            display.add_alert(f"Loaded {len(current_prices)} prices", "SUCCESS")
    except Exception as e:
        display.add_alert(f"KIS error: {str(e)[:20]}", "WARN")

    render_ui(full_refresh=True)

    # Calculate stats with current prices
    stats = _calculate_portfolio_stats(exchange_rate, current_prices)
    if "error" in stats:
        display.add_alert(f"Stats error: {stats['error']}", "ERROR")
        return

    while True:
        clear_result_area()

        # Build summary lines
        lines = []
        lines.append(f" [Portfolio] (Rate: {exchange_rate:,.2f} KRW/USD)")
        lines.append("─" * 80)
        lines.append(f" {'':10} │ {'USD':^27} │ {'KRW':^27} │ {'%':^6}")
        lines.append("─" * 80)

        def _align_pair(val1, val2, curr1, curr2, width=6):
            """Format and align two currency values for a table cell."""
            sym1 = "$ " if curr1 == "USD" else "₩ "
            sym2 = "$ " if curr2 == "USD" else "₩ "

            # Format number part
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

        # Cash ratio row (separate line)
        us_cash_str = f"{stats['us_cash_ratio']:>14.1f}        %"
        kr_cash_str = f"{stats['kr_cash_ratio']:>14.1f}        %"
        lines.append(f" {'Cash':10} │ {us_cash_str:27} │ {kr_cash_str:27} │")

        lines.append("─" * 80)
        lines.append(" 1. Create CSV   q. Exit")

        show_in_result_area(lines)

        choice = input_at(13, 2, "Enter Choice: ").strip().lower()

        if choice == '1':
            render_ui(full_refresh=True)
            export_portfolio_csv(current_prices)
            render_ui(full_refresh=True)
        elif choice == 'q':
            break
        else:
            pass


if __name__ == "__main__":
    # Quick test
    result = update_portfolio()
    if result:
        print("Portfolio sync completed successfully!")
    else:
        print("Portfolio sync failed!")


