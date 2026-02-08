# -*- coding: utf-8 -*-
"""
RAOEO Infinite Buying Method Module

This module automates the calculation and order placement for the
"Raoeo Infinite Buying Method" strategy.
"""
import os
import sys
import json
import logging
from utils import getch, getch_str, is_market_holiday
from datetime import datetime
from typing import Optional, Dict
import pytz

from kis.kis_api import kis_auth as ka
from display import show_in_result_area, input_at, add_alert
from data.data_service import get_portfolio_data
from kis.kis_api.overseas_stock.order.order import order as order_overseas
import trading_state
import trading_config

# Config directory (same as kis_auth.py)
CONFIG_ROOT = os.path.join(os.path.expanduser("~"), "KIS_config")
# Updated to use new config/history files
CONFIG_FILE = os.path.join(CONFIG_ROOT, "raoeo.json")
HISTORY_FILE = os.path.join(CONFIG_ROOT, "raoeo_history.json")

# LOC order type code for US stocks
LOC_ORDER_TYPE = "34"
LIMIT_ORDER_TYPE = "00"


def load_config() -> dict:
    """
    Load configuration from raoeo.json.
    """
    try:
        if not os.path.exists(CONFIG_FILE):
             # Fallback to old file if new one doesn't exist (during migration period)
             old_file = os.path.join(CONFIG_ROOT, "raoeo.json")
             if os.path.exists(old_file):
                 add_alert(f"New config not found, using old: {old_file}", "WARNING")
                 with open(old_file, 'r', encoding='utf-8') as f:
                     data = json.load(f)
                     # Adapt old format to new format structure strictly for internal use
                     old_config = data.get('config', {})
                     target = old_config.get('target')
                     if target:
                         return {"targets": {target: old_config}}
                     return {} # Invalid old config

        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return data # Returns dict with "targets" key
    except FileNotFoundError:
        add_alert(f"Config file not found: {CONFIG_FILE}", "ERROR")
        return {}
    except json.JSONDecodeError as e:
        add_alert(f"Invalid JSON in config: {e}", "ERROR")
        return {}


def get_current_price(symbol: str, exchange: str = "NASD") -> float:
    """
    Fetch current price for an overseas stock from WebSocket subscription.
    Returns 0.0 if data not yet received (caller should retry).
    """
    symbol_upper = symbol.upper()

    # Search through all keys in stock_data_state
    # Keys might be: "SOXL", "DNASSOXL", or other formats
    for key, data in trading_state.stock_data_state.items():
        # Check if key ends with the symbol (handles prefixes like DNAS, DNYS, etc.)
        if key.upper().endswith(symbol_upper) or key.upper() == symbol_upper:
            price_val = data.get('price', 0)
            if price_val > 0:
                return float(price_val)

    # Not found - WebSocket data not yet received
    return 0.0


def calculate_orders() -> dict:
    """
    Calculate buy/sell orders for today based on the RAOEO strategy for ALL targets.

    Returns:
        dict: Combined result with structure:
            {
                "date": "YYYY-MM-DD",
                "targets": {
                    "Ticker1": { ... },
                    "Ticker2": { ... }
                },
                "global_error": None
            }
    """
    tz_us = pytz.timezone('US/Eastern')
    today_str = datetime.now(tz_us).strftime("%Y-%m-%d")

    result = {
        "date": today_str,
        "targets": {},
        "global_error": None
    }

    # 1. Load config
    config_data = load_config()
    targets_config = config_data.get('targets', {})

    if not targets_config:
        result["global_error"] = "No targets configured in raoeo_new.json"
        return result

    # 2. Fetch Portfolio Data (Efficiency: Fetch once for all)
    portfolio = get_portfolio_data()
    if portfolio.get('error'):
         result["global_error"] = f"Portfolio Error: {portfolio['error']}"
         return result

    merged_holdings = portfolio.get('merged_data', {})

    # 3. Process each target
    for ticker, target_conf in targets_config.items():
        res_entry = _process_single_target(ticker, target_conf, merged_holdings)
        result["targets"][ticker] = res_entry

    return result


def _process_single_target(ticker: str, config: dict, portfolio_holdings: dict) -> dict:
    """
    Internal helper to calculate orders for a SINGLE target.
    """
    res = {
        "state": None,
        "config": config,
        "holdings": {},
        "daily_budget": 0.0,
        "orders": [],
        "error": None
    }

    # Validation
    required = ['seed', 'duration']
    for field in required:
        if field not in config:
            res["error"] = f"Missing config field: {field}"
            return res

    seed = float(config['seed'])
    duration = int(config['duration'])
    sell_profit = float(config.get('sell_profit', 0.10))
    exchange = config.get('exchange', 'NASD')

    # Resolve Exchange
    stock_info = trading_config.get_stock_info(ticker)
    if stock_info:
        mkt = stock_info.get('market', '').upper()
        excg_map = {"NASDAQ": "NASD", "NYSE": "NYSE", "AMEX": "AMEX", "NASDAQ/AMEX": "AMEX"}
        if mkt in excg_map:
            exchange = excg_map[mkt]
            res["config"]["exchange"] = exchange # Update back to res config

    # Daily Budget
    daily_budget = seed / duration
    res["daily_budget"] = round(daily_budget, 2)

    # Current Holdings
    qty = 0
    avg_price = 0.0
    cur_price_holding = 0.0

    # Search in merged holdings
    # merged_holdings keys are usually symbols
    if ticker in portfolio_holdings:
        info = portfolio_holdings[ticker]
        qty = int(info.get('qty', 0))
        total_investment = info.get('total_investment', 0)
        avg_price = total_investment / qty if qty > 0 else 0
        cur_price_holding = info.get('cur_price', 0)

    # Current Price Strategy: KIS API -> WebSocket -> Holdings
    from kis.wrapper import fetch_price
    cur_price = fetch_price(ticker)
    if cur_price <= 0:
        cur_price = get_current_price(ticker, exchange)
    if cur_price <= 0:
        cur_price = cur_price_holding

    res["holdings"] = {
        "qty": qty,
        "avg_price": round(avg_price, 2),
        "cur_price": cur_price
    }

    # Algorithm Logic
    spent_amount = avg_price * qty if qty > 0 else 0
    half_seed = seed / 2

    # Common Sell Logic
    if qty > 0 and avg_price > 0:
        sell_price = round(avg_price * (1 + sell_profit), 2)
        qty_lmt = (qty // 2) + (qty % 2)
        qty_loc = qty // 2

        if qty_lmt > 0:
            res["orders"].append({
                "type": "sell_limit",
                "price": sell_price,
                "qty": qty_lmt,
                "order_type": "LIMIT",
                "type_code": LIMIT_ORDER_TYPE,
                "desc": f"Sell limit {int(sell_profit*100)}% profit"
            })
        if qty_loc > 0:
            res["orders"].append({
                "type": "sell_loc",
                "price": sell_price,
                "qty": qty_loc,
                "order_type": "LOC",
                "type_code": LOC_ORDER_TYPE,
                "desc": f"Sell LOC {int(sell_profit*100)}% profit"
            })

    if spent_amount < half_seed:
        # Accumulating
        res["state"] = "accumulating"

        if qty > 0 and avg_price > 0:
             buy_ratio = 1 + sell_profit - 0.01
             buy_price = round(avg_price * buy_ratio, 2)
             buy_desc = f"Accumulating buy at {int(buy_ratio*100)}% of avg (avoid self-trade)"
        else:
             if cur_price <= 0:
                 res["error"] = f"Waiting for {ticker} price data."
                 return res
             buy_price = round(cur_price * 1.10, 2)
             buy_desc = "Accumulating buy at 110% of current price"

        buy_qty = int(daily_budget / buy_price)
        if buy_qty > 0:
            order_type_name = "buy_accumulating" if qty > 0 else "buy_initial"
            res["orders"].append({
                "type": order_type_name,
                "price": buy_price,
                "qty": buy_qty,
                "order_type": "LOC",
                "type_code": LOC_ORDER_TYPE,
                "desc": buy_desc
            })

    else:
        # Saturated
        res["state"] = "saturated"
        if avg_price <= 0:
            res["error"] = f"Invalid average price for {ticker}"
            return res

        total_buy_qty = int(daily_budget / avg_price)
        buy_qty_1 = (total_buy_qty // 2) + (total_buy_qty % 2)
        buy_qty_2 = total_buy_qty // 2

        # Buy 1: (Sell Profit - 1%)
        buy_ratio_1 = 1 + sell_profit - 0.01
        buy_price_1 = round(avg_price * buy_ratio_1, 2)

        if buy_qty_1 > 0:
            res["orders"].append({
                "type": "buy_guaranteed",
                "price": buy_price_1,
                "qty": buy_qty_1,
                "order_type": "LOC",
                "type_code": LOC_ORDER_TYPE,
                "desc": f"Buy at {int(buy_ratio_1*100)}% of avg (guaranteed)"
            })

        # Buy 2: 100% Avg
        buy_price_2 = round(avg_price * 1.00, 2)
        if buy_qty_2 > 0:
            res["orders"].append({
                "type": "buy_lower",
                "price": buy_price_2,
                "qty": buy_qty_2,
                "order_type": "LOC",
                "type_code": LOC_ORDER_TYPE,
                "desc": "Buy at 100% of avg (lower cost)"
            })

    return res


def execute_orders(orders_map: dict) -> Dict[str, list]:
    """
    Execute orders for multiple targets.

    Args:
        orders_map: Dict mapping ticker -> list of order dicts (from result['targets'][ticker]['orders'])

    Returns:
        Dict[str, list]: map of ticker -> execution results list
    """
    final_results = {}
    cano = ka.getTREnv().my_acct
    prod = ka.getTREnv().my_prod

    # We need to look up exchange for each ticker.
    # The caller typically has access to config, but here we might just rely on
    # the order object if we injected it, OR look it up again.
    # Ideally, the order object should have exchange info or we pass it.
    # Refactoring: Let's assume order dict itself DOES NOT have exchange.
    # We should get exchange from config.

    # Actually, execute_orders is called with a flat list in old code.
    # New design: We iterate through the `result['targets']` structure in `main.py` or wherever calls this.
    # But to keep `raoeo.py` self-contained/backward-ish compatible, let's accept `calculated_result`?
    # Or just `orders_map`.

    # Wait, the prompt implies `execute_orders` signature change.
    # Let's change signature to accept the `whole result object` or just the map.
    pass

def execute_all_orders(calculated_result: dict) -> dict:
    """
    Execute ALL orders found in the calculated result.

    Args:
        calculated_result: Return value from calculate_orders()

    Returns:
        dict: A map of ticker -> execution results list
    """
    execution_summary = {}

    cano = ka.getTREnv().my_acct
    prod = ka.getTREnv().my_prod

    targets_data = calculated_result.get('targets', {})

    for ticker, data in targets_data.items():
        orders = data.get('orders', [])
        config = data.get('config', {})
        exchange = config.get('exchange', 'NASD')

        ticker_results = []

        for order in orders:
             try:
                # Actual API Call
                df, err = order_overseas(
                    cano=cano,
                    acnt_prdt_cd=prod,
                    ovrs_excg_cd=exchange,
                    pdno=ticker,
                    ord_qty=str(order['qty']),
                    ovrs_ord_unpr=str(order['price']),
                    ord_dv="buy" if "buy" in order['type'].lower() else "sell",
                    ctac_tlno="",
                    mgco_aptm_odno="",
                    ord_svr_dvsn_cd="0",
                    ord_dvsn=order.get('type_code', LOC_ORDER_TYPE),
                    env_dv="real"
                )

                success = df is not None and not df.empty
                ticker_results.append({
                    "order": order,
                    "success": success,
                    "error": err if not success else None,
                    "response": df.to_dict('records') if success else None
                })
             except Exception as e:
                 ticker_results.append({
                    "order": order,
                    "success": False,
                    "error": str(e)
                })

        execution_summary[ticker] = ticker_results

    return execution_summary


def save_history(calculated_result: dict, execution_summary: dict = None) -> bool:
    """
    Save calculation and execution results to history file (New Format).
    """
    today_str = calculated_result.get('date')
    if not today_str:
         tz_us = pytz.timezone('US/Eastern')
         today_str = datetime.now(tz_us).strftime("%Y-%m-%d")

    # Update calculated_result with execution success/fail status
    if execution_summary:
        targets = calculated_result.get('targets', {})
        for ticker, t_res in targets.items():
            exec_res_list = execution_summary.get(ticker, [])
            for order in t_res.get('orders', []):
                # find matching result
                matched = next((r for r in exec_res_list if r['order'] == order), None)
                if matched:
                    order['success'] = matched['success']
                    order['error'] = matched.get('error')

    try:
        history_list = []
        if os.path.exists(HISTORY_FILE):
             with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                 history_list = json.load(f)

        # Find today's entry
        existing_idx = -1
        for idx, entry in enumerate(history_list):
            if entry.get('date') == today_str:
                existing_idx = idx
                break

        new_entry_targets = calculated_result.get('targets', {})

        if existing_idx >= 0:
            # Merge logic: verify if we need to merge specifically
            # Current logic: Replace or Merge?
            # If we calculated NEW orders for a ticker, we overwrite that ticker's entry.
            # But we should preserve other tickers if they exist in history but not in current run (unlikely if we run all)

            existing_entry = history_list[existing_idx]
            existing_targets = existing_entry.get('targets', {})

            # Merge
            for ticker, data in new_entry_targets.items():
                existing_targets[ticker] = data

            history_list[existing_idx]['targets'] = existing_targets

        else:
            # Insert New
            new_entry = {
                "date": today_str,
                "targets": new_entry_targets
            }
            history_list.insert(0, new_entry)

        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_list, f, indent=4, ensure_ascii=False)

        return True

    except Exception as e:
        add_alert(f"Failed to save history: {e}", "ERROR")
        return False


def check_today_history() -> Optional[dict]:
    """
    Check if RAOEO strategy was executed today.
    Returns the WHOLE list entry for today { "date":..., "targets":... } or None.
    """
    tz_us = pytz.timezone('US/Eastern')
    today_str = datetime.now(tz_us).strftime("%Y-%m-%d")

    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history_list = json.load(f)
                for entry in history_list:
                    if entry.get('date') == today_str:
                        return entry
    except Exception as e:
        add_alert(f"Error checking history: {e}", "ERROR")

    return None


def get_daily_report() -> dict:
    """
    Build RAOEO status report for both terminal and Telegram.
    Now supports MULTIPLE targets.

    Returns:
        dict: {
            "status": "executed" | "calculated" | "market_holiday" | "error",
            "global_error": ...,
            "targets": {
                 "SOXL": {
                     "status": ...,
                     "config": ...,
                     "holdings": ...,
                     "success_orders": [],
                     "failed_orders": [],
                     "pending_orders": []
                 },
                 ...
            }
        }
    """
    tz_us = pytz.timezone('US/Eastern')
    today_str = datetime.now(tz_us).strftime("%Y-%m-%d")

    report = {
         "date": today_str,
         "status": "init",
         "global_error": None,
         "targets": {}
    }

    # 1. Check History
    today_entry = check_today_history()

    # 2. Config & Portfolio (needed if calculating fresh)
    # We always try to load config to know what targets SHOULD exist
    config_data = load_config()
    targets_config = config_data.get('targets', {})

    if not targets_config:
        report["global_error"] = "No targets configured."
        return report

    # 3. Iterate all configured targets
    generated_portfolio = None

    # If we might need fresh data (holiday or calculation), fetch portfolio once
    if not today_entry:
        generated_portfolio = get_portfolio_data()

    calculated_fresh = None

    for ticker, conf in targets_config.items():
        t_report = {
            "status": "init",
            "config": conf,
            "holdings": None,
            "current_result": None,
            "success_orders": [],
            "failed_orders": [],
            "pending_orders": [],
            "error": None,
            "cur_price": 0.0
        }

        hist_data = None
        if today_entry and 'targets' in today_entry:
             hist_data = today_entry['targets'].get(ticker)

        if hist_data:
            # Found in history
            t_report["holdings"] = hist_data.get('holdings')
            t_report["config"] = hist_data.get('config') # Use history's config snapshot

            orders = hist_data.get('orders', [])
            all_success = True
            for o in orders:
                if o.get('success'):
                    t_report["success_orders"].append(o)
                else:
                    t_report["failed_orders"].append(o)
                    all_success = False

            if all_success and orders:
                t_report["status"] = "executed"
            elif t_report["failed_orders"]:
                t_report["status"] = "calculated" # Needs retry
                # Reconstruct 'current_result' subset for retry logic
                t_report["current_result"] = {
                    "orders": t_report["failed_orders"],
                    "state": hist_data.get('state'),
                    "is_retry": True
                }
            elif not orders:
                 t_report["status"] = "executed"

        else:
            # Not in history - Calculate Fresh OR Holiday Status

            # 1. Populate current Holdings if available
            if generated_portfolio:
                merged = generated_portfolio.get('merged_data', {})
                if ticker in merged:
                    info = merged[ticker]
                    qty = int(info.get('qty', 0))
                    total_inv = info.get('total_investment', 0)
                    avg_price = total_inv / qty if qty > 0 else 0
                    t_report["holdings"] = {
                        "qty": qty,
                        "avg_price": round(avg_price, 2),
                        "cur_price": info.get('cur_price', 0)
                    }
                else:
                     # Initial / Empty
                     t_report["holdings"] = {
                         "qty": 0, "avg_price": 0.0, "cur_price": 0.0
                     }

                     # If not held, try to fetch current price for reference
                     try:
                         # Use existing exchange config if available, or auto-detect
                         excsk = None
                         if config and 'exchange' in config:
                             excsk = config['exchange']

                         from kis import wrapper
                         fetched_price = wrapper.fetch_price(ticker, excsk)
                         if fetched_price > 0:
                             t_report["holdings"]["cur_price"] = fetched_price
                     except Exception as e_fetch:
                         logging.warning(f"Failed to fetch price for empty holding {ticker}: {e_fetch}")

            # 2. Check Holiday vs Calculation
            if not calculated_fresh:
                 # Market Holiday Check
                 if is_market_holiday("NYSE"):
                     report["status"] = "market_holiday"
                     # We already populated holdings above
                 else:
                     calculated_fresh = calculate_orders()

            if calculated_fresh:
                # Extract specific target result
                if calculated_fresh.get('global_error'):
                    report["global_error"] = calculated_fresh['global_error']

                t_data = calculated_fresh.get('targets', {}).get(ticker)

                if t_data:
                     t_report["current_result"] = t_data
                     # overwrite holdings with the one from calculation (should be same)
                     t_report["holdings"] = t_data.get('holdings')
                     t_report["config"] = t_data.get('config')

                     if t_data.get('error'):
                         t_report["error"] = t_data['error']
                         t_report["status"] = "error"
                     else:
                         t_report["status"] = "calculated"
                         # All orders are pending
                         t_report["pending_orders"] = t_data.get('orders', [])

            # Holiday Handling
            if is_market_holiday("NYSE"):
                 t_report["status"] = "market_holiday"

        # Common: Fetch current price (efficiency: could be batch, but per-ticker is fine for reporting)
        if t_report.get("config"):
            from kis.wrapper import fetch_price
            cp = fetch_price(ticker)
            if cp <= 0:
                cp = get_current_price(ticker, t_report["config"].get('exchange', 'NASD'))
            if cp <= 0 and t_report.get("holdings"):
                cp = t_report["holdings"].get("cur_price", 0)
            t_report["cur_price"] = cp

        report["targets"][ticker] = t_report

    # Aggregate Global Status
    # If ANY target is "calculated", global is "calculated" (needs action)
    # If ALL are "executed", global is "executed"
    statuses = [t["status"] for t in report["targets"].values()]

    if "error" in statuses:
        report["status"] = "error" # partial error
    elif "calculated" in statuses:
        report["status"] = "calculated"
    elif all(s == "executed" for s in statuses):
        report["status"] = "executed"
    elif "market_holiday" in statuses:
         report["status"] = "market_holiday"

    return report

# Backward compatibility wrappers if needed by existing callers
# (e.g. if main.py calls specific functions expecting old return types)
# Ideally main.py should be updated.
