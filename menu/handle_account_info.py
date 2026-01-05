"""
This module handles integrated account information inquiry for both KR and US markets.
It centralizes data fetching and provides an interactive terminal UI for portfolio monitoring.
"""
import msvcrt
import logging
import pandas as pd
from kis.kis_api import kis_auth as ka
from display import show_in_result_area, get_fixed_width_name
from kis.kis_api.domestic_stock.inquire_balance.inquire_balance import inquire_balance
from kis.kis_api.overseas_stock.inquire_present_balance.inquire_present_balance import inquire_present_balance
from .menu import MENU_DEBUG

def fetch_price(ticker: str, exchange: str = None) -> float:
    """
    Fetch current price for an overseas stock from KIS API.

    Args:
        ticker: Stock ticker symbol (e.g., 'QLD', 'SOXL')
        exchange: Exchange code (NAS, NYS, AMS). If None, auto-mapping via config.

    Returns:
        Current price as float, or 0.0 if failed
    """
    if not exchange:
        from trading_config import get_kis_exchange_code
        exchange = get_kis_exchange_code(ticker)

    from kis.kis_api.overseas_stock.price import price as price_module

    try:
        env_dv = "demo" if ka.isPaperTrading() else "real"
        df = price_module.price("", exchange, ticker.upper(), env_dv)

        if df is not None and not df.empty:
            row = df.iloc[0]

            # Try multiple possible field names for current price
            # 'last' is real-time price, 'base' is previous close (used when market is closed)
            price_fields = ['last', 'base', 'ovrs_stck_prpr', 'stck_prpr', 'prpr', 'clpr']
            for field in price_fields:
                if field in row:
                    val = row[field]
                    # Skip if value is None, empty string, or falsy (but not '0')
                    if val is None or val == '':
                        continue
                    try:
                        price_val = float(val)
                        if price_val > 0:
                            logging.info(f"[KIS API] {ticker} price fetched: {price_val} (field: {field})")
                            return price_val
                    except (ValueError, TypeError):
                        continue

            # No price found
            logging.warning(f"[KIS API] {ticker}: No valid price available in response")

        return 0.0

    except Exception as e:
        logging.warning(f"Failed to fetch price from KIS API for {ticker}: {e}")
        return 0.0


def print_account_info(data):
    """Render the account information UI and handle user navigation."""
    # State
    view_mode = 0 # 0: Summary, 1: US List, 2: KR List
    page_idx = 0
    ROWS_PER_PAGE = 5

    # Pre-calc Summary Data
    ex_rate = data.get('exchange_rate', 0.0)

    # --- KR Summary ---
    d_orderable = data.get('krw_orderable', 0)

    d_pl_amt = 0.0
    d_pchs_amt = 0.0
    for stock in data['domestic_stocks']:
        d_pl_amt += stock['pnl_amt']
        d_pchs_amt += (stock['avg_price'] * stock['qty'])

    d_stock_eval = d_pchs_amt + d_pl_amt
    d_tot_assets = d_stock_eval + d_orderable
    d_pl_rate = (d_pl_amt / d_pchs_amt * 100) if d_pchs_amt > 0 else 0.0

    # --- US Summary ---
    o_asset = data['overseas_asset']
    o_orderable_usd = float(o_asset.get('frcr_drwg_psbl_amt_1', 0))

    o_pl_amt_usd = 0.0
    o_pchs_amt_usd = 0.0
    o_stock_eval_usd = 0.0

    for stock in data['overseas_stocks']:
        o_pl_amt_usd += stock['pnl_amt']
        pchs = stock['avg_price'] * stock['qty']
        o_pchs_amt_usd += pchs
        o_stock_eval_usd += (stock['cur_price'] * stock['qty'])

    o_pl_rate = (o_pl_amt_usd / o_pchs_amt_usd * 100) if o_pchs_amt_usd > 0 else 0.0
    o_tot_assets_usd = o_stock_eval_usd + o_orderable_usd

    while True:
        lines = []
        SEPARATOR_LEN = 95

        # --- VIEW 0: SUMMARY ---
        if view_mode == 0:
            lines.append("=" * SEPARATOR_LEN)
            lines.append(f" [Account Summary] exchange rate : {ex_rate:,.2f} KRW/USD")
            lines.append("=" * SEPARATOR_LEN)
            lines.append(f" [KR] Total assets: {d_tot_assets:,.0f} KRW | Orderable: {d_orderable:,.0f} KRW")
            lines.append(f"      PL Amt      : {d_pl_amt:,.0f} KRW ({d_pl_rate:+.2f} %)")
            lines.append("-" * SEPARATOR_LEN)
            lines.append(f" [US] Total assets: ${o_tot_assets_usd:,.2f} | Orderable: ${o_orderable_usd:,.2f}")
            lines.append(f"      PL Amt      : ${o_pl_amt_usd:,.2f} ({o_pl_rate:+.2f} %)")
            lines.append("=" * SEPARATOR_LEN)
            lines.append(f" [f] Toggle View(US List)  [q] Quit")

        # --- VIEW 1 & 2: LIST ---
        else:
            is_us = (view_mode == 1)
            target_list = data['overseas_stocks'] if is_us else data['domestic_stocks']
            title = "US Stocks" if is_us else "KR Stocks"

            l_pl_amt = o_pl_amt_usd if is_us else d_pl_amt
            l_pl_rate = o_pl_rate if is_us else d_pl_rate
            l_stock_eval = o_stock_eval_usd if is_us else d_stock_eval

            total_items = len(target_list)
            total_pages = (total_items + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
            if total_pages == 0: total_pages = 1
            if page_idx >= total_pages: page_idx = 0

            lines.append(f" [Portfolio: {title}] ({page_idx+1}/{total_pages})")

            # Header
            header_fmt = " {:<6} | {} | {:>6} | {:>9} | {:>9} | {:>9} | {:>7}"
            hdr_name = get_fixed_width_name("Name", 20)
            lines.append(header_fmt.format("Ticker", hdr_name, "Qty", "Avg", "Cur", "P/L", "P/L%"))
            lines.append("=" * SEPARATOR_LEN)

            start_idx = page_idx * ROWS_PER_PAGE
            end_idx = start_idx + ROWS_PER_PAGE
            page_items = target_list[start_idx:end_idx]

            if not page_items:
                lines.append("  (No holdings)")
                for _ in range(ROWS_PER_PAGE-1): lines.append("")
            else:
                for item in page_items:
                    ticker = str(item.get('symbol', ''))[:6]
                    name = get_fixed_width_name(item['name'], 20)
                    if is_us:
                        q_val = item['qty']
                        qty = f"{int(q_val):,}" if q_val.is_integer() else f"{q_val:,.2f}"
                        avg = f"${item['avg_price']:,.2f}"
                        cur = f"${item['cur_price']:,.2f}"
                        pl_val = f"${item['pnl_amt']:,.2f}"
                    else:
                        qty = f"{item['qty']:,}"
                        avg = f"{item['avg_price']:,.0f}"
                        cur = f"{item['cur_price']:,.0f}"
                        pl_val = f"{item['pnl_amt']:,.0f}"

                    pnl_pct = f"{item['pnl_rate']:.2f}%"
                    lines.append(header_fmt.format(ticker, name, qty, avg, cur, pl_val, pnl_pct))

                rem = ROWS_PER_PAGE - len(page_items)
                for _ in range(rem): lines.append("")

            lines.append("-" * SEPARATOR_LEN)
            rate_str = f"{l_pl_rate:+.2f}%"
            if l_pl_amt < 0 and "0.00%" in rate_str and "+" in rate_str:
                rate_str = rate_str.replace("+", "-")

            if is_us:
                tot_str = f" Total: ${l_stock_eval:,.2f}       P/L: ${l_pl_amt:,.2f} ({rate_str})"
            else:
                tot_str = f" Total: {l_stock_eval:,.0f} KRW       P/L: {l_pl_amt:,.0f} KRW ({rate_str})"
            lines.append(tot_str)

            next_view = "KR List" if is_us else "Summary"
            lines.append(f" [n] Next Page  [f] Toggle({next_view})  [q] Quit")

        show_in_result_area(lines)

        ch = msvcrt.getch()
        if ch == b'q':
            break
        elif ch == b'f':
            view_mode = (view_mode + 1) % 3
            page_idx = 0
        elif ch == b'n':
            if view_mode != 0:
                page_idx += 1
                if page_idx >= total_pages: page_idx = 0

def handle_account_info():
    """Main menu controller for account information."""
    from data.data_service import get_portfolio_data, convert_portfolio_to_account_format

    show_in_result_area(["Fetching integrated account data..."])

    # Get portfolio data via cache/KIS Thread
    portfolio = get_portfolio_data()

    if portfolio.get("error"):
        show_in_result_area([f"Error: {portfolio['error']}"])
        return

    # Convert to the format expected by print_account_info
    data = convert_portfolio_to_account_format(portfolio)
    print_account_info(data)

