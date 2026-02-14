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

from strategy import storage

# LOC order type code for US stocks
LOC_ORDER_TYPE = "34"
LIMIT_ORDER_TYPE = "00"


def load_config() -> dict:
    """
    Load configuration from strategy_config.json via storage module.
    """
    return storage.get_strategy_config("raoeo")


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

    # Common Sell Logic (keep at least 1 share)
    if qty > 1 and avg_price > 0:
        sellable = qty - 1
        sell_price = round(avg_price * (1 + sell_profit), 2)
        qty_lmt = (sellable // 2) + (sellable % 2)
        qty_loc = sellable // 2

        if qty_lmt > 0:
            res["orders"].append({
                "type": "sell_limit",
                "price": sell_price,
                "qty": qty_lmt,
                "order_type": "LIMIT",
                "type_code": LIMIT_ORDER_TYPE,
                "exchange": exchange,
                "desc": f"Sell limit {int(sell_profit*100)}% profit"
            })
        if qty_loc > 0:
            res["orders"].append({
                "type": "sell_loc",
                "price": sell_price,
                "qty": qty_loc,
                "order_type": "LOC",
                "type_code": LOC_ORDER_TYPE,
                "exchange": exchange,
                "desc": f"Sell LOC {int(sell_profit*100)}% profit"
            })

    ten_pct_seed = seed * 0.1

    if spent_amount < ten_pct_seed:
        # Phase 0: Holdings < 10% of seed
        res["state"] = "phase_0"

        if avg_price <= 0:
            res["error"] = f"Phase 0: No avg_price for {ticker}. Check holdings."
            return res

        # Order 1: 100% of daily budget at avg*(1+sell_profit-0.01)
        buy_price_1 = round(avg_price * (1 + sell_profit - 0.01), 2)
        buy_qty_1 = int(daily_budget / buy_price_1)
        if buy_qty_1 < 1:
            buy_qty_1 = 1

        res["orders"].append({
            "type": "buy_phase0_main",
            "price": buy_price_1,
            "qty": buy_qty_1,
            "order_type": "LOC",
            "type_code": LOC_ORDER_TYPE,
            "exchange": exchange,
            "desc": f"Phase0: Buy at avg*{(1+sell_profit-0.01)*100:.0f}% = ${buy_price_1}"
        })

        # Order 2: (seed_10pct_qty - qty - buy_qty_1) at avg*95%
        seed_10pct_qty = int(ten_pct_seed / avg_price)
        remaining_qty = seed_10pct_qty - qty - buy_qty_1

        if remaining_qty > 0:
            buy_price_2 = round(avg_price * 0.95, 2)
            res["orders"].append({
                "type": "buy_phase0_fill",
                "price": buy_price_2,
                "qty": remaining_qty,
                "order_type": "LOC",
                "type_code": LOC_ORDER_TYPE,
                "exchange": exchange,
                "desc": f"Phase0: Fill to 10% seed at avg*95% = ${buy_price_2}"
            })

    elif spent_amount < half_seed:
        # Phase 1: 10% <= spent < seed/2
        res["state"] = "phase_1"

        if avg_price <= 0:
            res["error"] = f"Phase 1: No avg_price for {ticker}. Check holdings."
            return res

        # Order: 100% of daily budget at avg*(1+sell_profit-0.01)
        buy_price = round(avg_price * (1 + sell_profit - 0.01), 2)
        buy_qty = int(daily_budget / buy_price)
        if buy_qty < 1:
            buy_qty = 1

        res["orders"].append({
            "type": "buy_phase1",
            "price": buy_price,
            "qty": buy_qty,
            "order_type": "LOC",
            "type_code": LOC_ORDER_TYPE,
            "exchange": exchange,
            "desc": f"Phase1: Buy at avg*{(1+sell_profit-0.01)*100:.0f}% = ${buy_price}"
        })

    else:
        # Phase 2: spent >= seed/2
        res["state"] = "phase_2"

        if avg_price <= 0:
            res["error"] = f"Phase 2: No avg_price for {ticker}. Check holdings."
            return res

        # Order 1: 50% of daily budget at avg*100%
        buy_price_1 = round(avg_price, 2)
        total_buy_qty = int(daily_budget / avg_price)
        buy_qty_1 = total_buy_qty // 2
        if buy_qty_1 < 1:
            buy_qty_1 = 1

        res["orders"].append({
            "type": "buy_phase2_avg",
            "price": buy_price_1,
            "qty": buy_qty_1,
            "order_type": "LOC",
            "type_code": LOC_ORDER_TYPE,
            "exchange": exchange,
            "desc": f"Phase2: Buy 50% at avg = ${buy_price_1}"
        })

        # Order 2: 50% of daily budget at avg*(1+sell_profit-0.01)
        buy_price_2 = round(avg_price * (1 + sell_profit - 0.01), 2)
        buy_qty_2 = total_buy_qty - buy_qty_1
        if buy_qty_2 < 1:
            buy_qty_2 = 1

        res["orders"].append({
            "type": "buy_phase2_upper",
            "price": buy_price_2,
            "qty": buy_qty_2,
            "order_type": "LOC",
            "type_code": LOC_ORDER_TYPE,
            "exchange": exchange,
            "desc": f"Phase2: Buy 50% at avg*{(1+sell_profit-0.01)*100:.0f}% = ${buy_price_2}"
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
        config_exchange = config.get('exchange', 'NASD')

        ticker_results = []

        for order in orders:
             try:
                # Get exchange from order first, then fallback to config
                exchange = order.get('exchange') or config_exchange

                # Map exchange code for order API (different from quote API)
                # Quote API uses: NAS, NYS, AMS
                # Order API uses: NASD, NYSE, AMEX
                order_exchange_map = {
                    'AMS': 'AMEX',
                    'NAS': 'NASD',
                    'NYS': 'NYSE'
                }
                order_exchange = order_exchange_map.get(exchange, exchange)

                # Actual API Call
                df, err = order_overseas(
                    cano=cano,
                    acnt_prdt_cd=prod,
                    ovrs_excg_cd=order_exchange,
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
        history_list = storage.load_history("raoeo")
        if not isinstance(history_list, list):
             history_list = []

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

        return storage.save_history("raoeo", history_list)

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
        history_list = storage.load_history("raoeo")
        if isinstance(history_list, list):
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
