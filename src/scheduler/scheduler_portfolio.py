# -*- coding: utf-8 -*-
"""
Portfolio Report Service
Handles daily portfolio summary and reporting logic (typically for 7 AM).
"""
import logging
import os
import json
import glob
import re
from datetime import datetime, timedelta
from typing import Optional

from core.constants import CONFIG_ROOT, DEFAULT_USD_KRW_EXCHANGE_RATE
from telegram_bot.telegram_portfolio import format_portfolio_summary
from telegram_bot.telegram_utils import send_notification
from data.data_service import get_portfolio_data

# Configuration
HISTORY_DIR = os.path.join(CONFIG_ROOT, "portfolio_history")
# User requested to keep reports in the same folder as history
REPORTS_DIR = HISTORY_DIR

# Ensure directories exist
os.makedirs(HISTORY_DIR, exist_ok=True)


def load_historical_data(target_date: str) -> Optional[dict]:
    """Load portfolio data for a specific date (YYYYMMDD)."""
    file_path = os.path.join(HISTORY_DIR, f"portfolio_{target_date}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"[Scheduler] Failed to load history {file_path}: {e}")
    return None


def get_sorted_history_files() -> list[str]:
    """Return sorted list of portfolio history file paths."""
    pattern = os.path.join(HISTORY_DIR, "portfolio_*.json")
    files = glob.glob(pattern)
    files.sort()  # Sort by filename (date)
    return files


def calculate_diff(current: float, previous: float) -> tuple[float, float]:
    """Calculate value difference and percentage change."""
    if previous == 0:
        return 0.0, 0.0
    diff = current - previous
    pct = (diff / previous) * 100
    return diff, pct


def get_comparison_stats(current_data: dict, history_files: list[str], current_file_path: str) -> str:
    """
    Generate comparison statistics text.

    Args:
        current_data: Current portfolio data
        history_files: Sorted list of all history files (including potentially the current one if saved)
        current_file_path: Path of the current file to exclude from "past" list if present

    Returns:
        Formatted comparison string
    """
    # Filter out current file from history to find actual past files
    past_files = [f for f in history_files if f != current_file_path]

    if not past_files:
        return ""

    comparison_lines = ["", "📊 <b>Performance Insight</b>"]

    # Compare against the most recent daily, weekly, and monthly history points.
    targets = [
        ("1 Day", -1),
        ("1 Week", -5),
        ("1 Month", -20)
    ]

    # Read the current raw holdings and cash snapshots.
    curr_holdings = current_data.get('holdings', [])
    curr_cash = current_data.get('cash_holdings', [])

    # Saved history files can be raw or processed, so calculate totals from the
    # richest available fields and fall back to holdings plus cash.

    def get_total_equity(data: dict) -> float:
        """Calculate Total Equity in KRW"""
        # 1. Prefer pre-calculated KRW stats when present.
        stats = data.get('stats', {})
        # Keys may exist with a valid zero value.
        if 'total_stock_krw' in stats and 'total_cash_krw' in stats:
            return stats.get('total_stock_krw', 0) + stats.get('total_cash_krw', 0)

        # 2. Otherwise derive KRW equity from holdings and cash.
        total_krw = 0.0
        # Prefer metadata exchange rate, then the legacy top-level field.
        exchange_rate = data.get('metadata', {}).get('exchange_rate')
        if not exchange_rate:
            exchange_rate = data.get('exchange_rate', DEFAULT_USD_KRW_EXCHANGE_RATE)

        merged_data = data.get('merged_data', {})

        for h in data.get('holdings', []):
             ticker = h.get('ticker')

             # Default to USD unless metadata identifies a KRW asset.
             currency = 'USD'
             if ticker in merged_data:
                 currency = merged_data[ticker].get('currency', 'USD')
             else:
                 # Use asset metadata or ticker shape when merged data is absent.
                 asset_info = data.get('asset_info', {}).get(ticker, {})
                 market = asset_info.get('market', 'US')
                 if market == 'KR' or (len(ticker) == 6 and ticker.isdigit()):
                     currency = 'KRW'

             val = h.get('qty', 0) * h.get('cur_price', 0)
             if currency == 'USD':
                 total_krw += val * exchange_rate
             else:
                 total_krw += val

        for c in data.get('cash_holdings', []):
            if c.get('currency') == 'USD':
                total_krw += c.get('amount', 0) * exchange_rate
            else:
                total_krw += c.get('amount', 0)

        return total_krw

    def get_total_equity_usd(data: dict) -> float:
        """Calculate Total Equity in USD"""
        # 1. Prefer processed total_value_usd when present.
        if data.get('total_value_usd'):
            return float(data['total_value_usd'])

        # 2. Fall back to pre-calculated USD stats.
        stats = data.get('stats', {})
        if 'total_stock_usd' in stats and 'total_cash_usd' in stats:
            return stats.get('total_stock_usd', 0) + stats.get('total_cash_usd', 0)

        # 3. Derive USD equity from KRW totals as the last resort.
        total_krw = get_total_equity(data)
        exchange_rate = data.get('metadata', {}).get('exchange_rate')
        if not exchange_rate:
            exchange_rate = data.get('exchange_rate', DEFAULT_USD_KRW_EXCHANGE_RATE)

        if exchange_rate > 0:
            return total_krw / exchange_rate
        return 0.0

    current_total_krw = get_total_equity(current_data)
    current_total_usd = get_total_equity_usd(current_data)

    for label, idx in targets:
        if abs(idx) <= len(past_files):
            target_file = past_files[idx]
            try:
                with open(target_file, 'r', encoding='utf-8') as f:
                    past_data = json.load(f)

                past_total_krw = get_total_equity(past_data)
                past_total_usd = get_total_equity_usd(past_data)

                # Calculate KRW stats
                diff_krw, pct_krw = calculate_diff(current_total_krw, past_total_krw)
                emoji_krw = "🔺" if pct_krw > 0 else "🔻" if pct_krw < 0 else "➖"

                # Calculate USD stats
                diff_usd, pct_usd = calculate_diff(current_total_usd, past_total_usd)
                emoji_usd = "🔺" if pct_usd > 0 else "🔻" if pct_usd < 0 else "➖"

                # Format Option: Simplified (Change Only)
                # <b>📅 1 Day</b>
                # <code>
                # 🇰🇷 🔺  +1,234 k,  +1.20%
                # 🇺🇸 🔺    +123,  +1.00%
                # </code>

                # KRW Diff: 1k unit (space added as requested: "+8,970 k")
                str_krw_diff = f"{diff_krw/1000:+,.0f} k"
                str_krw_pct = f"{pct_krw:+.2f}%"

                # USD Diff: Standard
                str_usd_diff = f"{diff_usd:+,.0f}"
                str_usd_pct = f"{pct_usd:+.2f}%"

                # Construct aligned lines
                # Padding:
                # Emoji: fixed
                # Diff: ~10 chars
                # Pct: ~7 chars

                line_krw = f"🇰🇷 {emoji_krw} {str_krw_diff:>10}, {str_krw_pct:>7}"
                line_usd = f"🇺🇸 {emoji_usd} {str_usd_diff:>10}, {str_usd_pct:>7}"

                line_header = f"<b>📅 {label}</b>"

                comparison_lines.append(f"{line_header}\n<code>{line_krw}\n{line_usd}</code>")
            except Exception as e:
                logging.warning(f"Error comparing {label}: {e}")

    # Top Movers (vs Yesterday only)
    if past_files:
        try:
            last_file = past_files[-1]
            with open(last_file, 'r', encoding='utf-8') as f:
                yesterday_data = json.load(f)

            # Build price map
            y_prices = {h['ticker']: h.get('cur_price', 0) for h in yesterday_data.get('holdings', [])}

            # Deduplicate current holdings by ticker
            # Use a dictionary to track unique tickers.
            # If a ticker appears multiple times, we just take the first one found
            # (assuming cur_price is same for same ticker).
            unique_holdings = {}
            for h in curr_holdings:
                ticker = h['ticker']
                if ticker not in unique_holdings:
                    unique_holdings[ticker] = h

            movers = []
            for ticker, h in unique_holdings.items():
                cur_p = h.get('cur_price', 0)
                old_p = y_prices.get(ticker, 0)

                if old_p > 0:
                    chg_pct = ((cur_p - old_p) / old_p) * 100
                    movers.append((ticker, chg_pct, h.get('name', ticker)))

            # Sort by abs change
            movers.sort(key=lambda x: abs(x[1]), reverse=True)

            if movers:
                comparison_lines.append("")
                comparison_lines.append("🚀 <b>Top Movers</b>")
                for t, pct, name in movers[:3]: # Top 3
                     icon = "🔥" if pct > 0 else "💧"
                     comparison_lines.append(f"{icon} <b>{name}</b>: {pct:+.1f}%")

        except Exception as e:
            logging.warning(f"Error calculating movers: {e}")

    return "\n".join(comparison_lines)


def run_daily_portfolio_report():
    """
    Execute daily portfolio reporting routine (typically scheduled for morning).
    - Tue-Sat: Collect Data (Save JSON) + Send Notification.
    - Mon: Load Friday's data (no fetch) + Resend report for week-start review.
    - Sun: Skip.
    """
    now = datetime.now()
    weekday = now.weekday() # Mon=0, Sun=6

    # Skip Sunday (6) completely
    if weekday == 6:
        logging.info("[Scheduler] Sunday - Skipping daily job.")
        return

    logging.info(f"[Scheduler] Starting daily job. Weekday: {weekday}")

    portfolio_data = None
    current_file_path = None

    # Monday (0): Load most recent saved file (Friday's data) for week-start review
    # No new data fetch, just resend Friday's report
    if weekday == 0:
        history_files = get_sorted_history_files()
        if history_files:
            # Load the most recent file (should be Friday's data)
            latest_file = history_files[-1]
            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    portfolio_data = json.load(f)
                current_file_path = latest_file
                logging.info(f"[Scheduler] Monday - Loaded Friday's data from {latest_file}")
            except Exception as e:
                logging.error(f"[Scheduler] Failed to load Friday's data: {e}")
                send_notification(f"⚠️ Monday report failed: Could not load Friday's data")
                return
        else:
            logging.warning("[Scheduler] Monday - No history files found")
            send_notification("⚠️ Monday report: No historical data available")
            return
    else:
        # Tue(1) ~ Sat(5): Fetch new data and save
        # For file naming, 7AM today = "Yesterday's Close"
        yesterday = now - timedelta(days=1)
        date_str = yesterday.strftime("%Y%m%d")
        current_file_path = os.path.join(HISTORY_DIR, f"portfolio_{date_str}.json")

        # Check if file already exists (avoid duplicate fetch on manual trigger)
        if os.path.exists(current_file_path):
            try:
                with open(current_file_path, 'r', encoding='utf-8') as f:
                    portfolio_data = json.load(f)
                logging.info(f"[Scheduler] Loaded existing portfolio data from {current_file_path}")
            except Exception as e:
                logging.error(f"[Scheduler] Failed to load existing file: {e}")
                portfolio_data = None

        if portfolio_data is None:
            try:
                # Use rich data service for both saving and display
                portfolio_data = get_portfolio_data()
            except Exception as e:
                if "Timeout" in str(e):
                    error_msg = f"⚠️ [네트워크 타임아웃] KIS API 무응답 (Portfolio Data): {e}"
                else:
                    error_msg = f"[Scheduler] Failed to get portfolio: {e}"
                logging.error(error_msg)
                send_notification(error_msg)
                return

            # Save data (Tue-Sat)
            try:
                with open(current_file_path, 'w', encoding='utf-8') as f:
                    json.dump(portfolio_data, f, ensure_ascii=False, indent=2)
                logging.info(f"[Scheduler] Saved portfolio data to {current_file_path}")
            except Exception as e:
                logging.error(f"[Scheduler] Failed to save file: {e}")

    # Send the portfolio report once data and the history file path are ready.
    if portfolio_data:
        try:
            # Generate Message
            summary_text = format_portfolio_summary(portfolio_data)

            # Generate History Comparison
            history_files = get_sorted_history_files()
            comparison_text = get_comparison_stats(portfolio_data, history_files, current_file_path)

            final_message = f"{summary_text}\n{comparison_text}"

            # Extract date_str from current_file_path for backup naming
            # e.g., portfolio_20260207.json -> 20260207
            match = re.search(r'portfolio_(\d{8})\.json', current_file_path)
            date_str = match.group(1) if match else datetime.now().strftime("%Y%m%d")

            # Backup Report
            report_file = os.path.join(REPORTS_DIR, f"report_{date_str}.txt")
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(final_message)

            # Send
            send_notification(final_message)
            logging.info("[Scheduler] Notification sent and report backed up.")

        except Exception as e:
            logging.error(f"[Scheduler] Notification failed: {e}")
            send_notification(f"⚠️ Scheduler Error: {e}")
