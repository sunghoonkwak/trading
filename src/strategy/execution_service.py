# -*- coding: utf-8 -*-
"""
Strategy Execution Service (Centralized)

This module handles the orchestration of strategy execution, including:
1. Fetching data (Portfolio, Prices, History)
2. Calculating orders (via pure strategy modules)
3. Executing orders (via KIS API)
4. Saving history
5. Generating reports
"""
import logging
import json
from datetime import datetime
import pytz
from typing import Dict, List, Tuple, Any

from strategy import raoeo, value_averaging, rebalancing
from strategy.base import StrategyOrder, OrderSide
from data.config_manager import ConfigFile, load_json, save_json
from utils.market_utils import is_market_holiday
from kis import wrapper
from kis.kis_api import kis_auth as ka
from kis.kis_api.overseas_stock.order.order import order as order_overseas_stock
from data.data_service import get_portfolio_data

# -------------------------------------------------------------------------
# Common Helpers
# -------------------------------------------------------------------------

def get_market_data() -> Tuple[Dict, Dict]:
    """
    Fetch current portfolio and prices for all configured strategy targets.
    Returns: (portfolio_holdings, current_prices_map)
    """
    # 1. Portfolio
    portfolio = get_portfolio_data(scope="kis")
    holdings = portfolio.get('merged_data', {})

    # 2. Config & Prices
    strategy_config = load_json(ConfigFile.STRATEGY_CONFIG, default={})
    raoeo_conf = strategy_config.get('raoeo', {}).get('targets', {})
    va_conf = strategy_config.get('value_averaging', {}).get('targets', {})
    reb_conf = strategy_config.get('rebalancing', {}).get('assets', [])

    reb_tickers = {a['ticker'] for a in reb_conf}
    all_tickers = set(raoeo_conf.keys()) | set(va_conf.keys()) | reb_tickers
    current_prices = {}

    for t in all_tickers:
        # Try fetching real-time price
        price = wrapper.fetch_price(t)
        if price > 0:
            current_prices[t] = price
        else:
            # Fallback: check portfolio if held
            if t in holdings:
                current_prices[t] = float(holdings[t].get('cur_price', 0))

    return holdings, current_prices

def execute_single_order(order: StrategyOrder) -> Tuple[bool, str]:
    """Execute a single strategy order via KIS API."""
    try:
        cano = ka.getTREnv().my_acct
        acnt_prdt_cd = ka.getTREnv().my_prod

        ord_dv = "buy" if order.side == OrderSide.BUY else "sell"

        # Price protection for Market Sell (US)
        # If price is 0 and it's a SELL, we use a very low price to act as Market Sell
        exec_price = order.price
        exec_type = order.order_type
        if order.side == OrderSide.SELL and order.price == 0:
            exec_price = 0.01 # Market-like sell for US Limit
            exec_type = "00"  # Limit

        # Simple Exchange Mapping
        stock_info = wrapper.get_stock_info(order.symbol)
        market = stock_info.get('market', 'NASD')
        exchange_map = {"NAS": "NASD", "NYS": "NYSE", "AMS": "AMEX"}
        ovrs_excg_cd = exchange_map.get(market, market)

        res, err = order_overseas_stock(
            cano=cano,
            acnt_prdt_cd=acnt_prdt_cd,
            ovrs_excg_cd=ovrs_excg_cd,
            pdno=order.symbol,
            ord_qty=str(order.quantity),
            ovrs_ord_unpr=str(exec_price),
            ord_dv=ord_dv,
            ctac_tlno="",
            mgco_aptm_odno="",
            ord_svr_dvsn_cd="0",
            ord_dvsn=exec_type,
            env_dv="real"
        )

        if res is not None and not res.empty:
            return True, "Success"
        return False, str(err)
    except Exception as e:
        return False, str(e)

# -------------------------------------------------------------------------
# RAOEO Execution
# -------------------------------------------------------------------------

def run_raoeo_strategy(execute: bool = False) -> Dict[str, Any]:
    """
    Run RAOEO strategy cycle.

    Args:
        execute: If True, executes the calculated orders.

    Returns:
        Dict containing report data:
        {
            "date": "YYYY-MM-DD",
            "status": "market_holiday" | "executed" | "calculated" | "error",
            "orders": [StrategyOrder objects...],
            "execution_results": [{"order": ..., "success": True, "message": ...}, ...],
            "holdings": {...},
            "config": {...}, # Added config to report
            "error": str
        }
    """
    today_str = datetime.now(pytz.timezone('US/Eastern')).strftime("%Y-%m-%d")
    report = {
        "date": today_str,
        "status": "init",
        "orders": [],
        "execution_results": [],
        "holdings": {},
        "config": {},
        "error": None
    }

    try:
        # 1. Load Data
        holdings, prices = get_market_data()
        report["holdings"] = holdings

        strategy_config = load_json(ConfigFile.STRATEGY_CONFIG, default={})
        raoeo_conf = strategy_config.get('raoeo', {}).get('targets', {})
        report["config"] = raoeo_conf

        # 2. Check Holiday (but still return data)
        is_holiday = is_market_holiday("NYSE", today_str)

        if not is_holiday:
            # 3. Calculate (Only if not holiday)
            orders = raoeo.calculate_orders(
                targets_config=raoeo_conf,
                portfolio=holdings,
                current_prices=prices
            )
            report["orders"] = orders

            if not orders:
                report["status"] = "no_orders"
            else:
                report["status"] = "calculated"
        else:
            report["status"] = "market_holiday"

        # 4. Execute (if requested and possible)
        if execute and report["status"] == "calculated":
            results = []
            success_count = 0

            for order in orders:
                success, msg = execute_single_order(order)
                results.append({
                    "order": order,
                    "success": success,
                    "message": msg
                })
                if success: success_count += 1

            report["execution_results"] = results

            if success_count == len(orders):
                report["status"] = "executed"
            else:
                report["status"] = "partial_execution"

            # TODO: Save History Logic (Optional, but recommended)
            # save_raoeo_history(orders, results)

    except Exception as e:
        logging.error(f"RAOEO Service Error: {e}", exc_info=True)
        report["status"] = "error"
        report["error"] = str(e)

    return report

# -------------------------------------------------------------------------
# Value Averaging Execution
# -------------------------------------------------------------------------

def run_va_strategy(execute: bool = False) -> Dict[str, Any]:
    """
    Run Value Averaging strategy cycle.

    Args:
        execute: If True, executes orders and saves history.

    Returns:
        Dict containing report data (similar structure to RAOEO).
    """
    today_str = datetime.now(pytz.timezone('US/Eastern')).strftime("%Y-%m-%d")
    report = {
        "date": today_str,
        "status": "init",
        "orders": [],
        "execution_results": [],
        "context": {}, # For debugging/logging
        "error": None
    }

    try:
        # 1. Load Data
        holdings, prices = get_market_data()

        strategy_config = load_json(ConfigFile.STRATEGY_CONFIG, default={})
        va_conf = strategy_config.get('value_averaging', {}).get('targets', {})
        va_history = load_json(ConfigFile.VA_HISTORY, default=[])

        # 2. Calculate (Always calculate for VA, even on holiday to show status)
        orders, context = value_averaging.calculate_orders(
            targets_config=va_conf,
            portfolio=holdings,
            current_prices=prices,
            history_data=va_history,
            today_date=today_str
        )

        report["orders"] = orders
        report["context"] = context

        # Check Status
        is_holiday = is_market_holiday("NYSE", today_str)

        if is_holiday:
            report["status"] = "market_holiday"
        elif not orders:
            report["status"] = "no_orders"
        else:
            report["status"] = "calculated"

        # 3. Execute (if requested and possible)
        # Only execute if calculated orders exist and NOT holiday
        if execute and report["status"] == "calculated":
            results = []
            success_count = 0

            for order in orders:
                success, msg = execute_single_order(order)
                results.append({
                    "order": order,
                    "success": success,
                    "message": msg
                })

                # Save Individual Result
                _save_va_history_entry(
                    ticker=order.symbol,
                    context=context.get(order.symbol, {}),
                    order=order,
                    success=success,
                    message=msg
                )

                if success: success_count += 1

            # Save Skips (targets with no orders)
            _save_va_skips(context, orders)

            report["execution_results"] = results

            if success_count == len(orders):
                report["status"] = "executed"
            else:
                report["status"] = "partial_execution"

        # Even if holiday, if execute=True requested (by scheduler/user force), we might want to log?
        # But usually we skip execution on holiday.

    except Exception as e:
        logging.error(f"VA Service Error: {e}", exc_info=True)
        report["status"] = "error"
        report["error"] = str(e)

    return report

def _save_va_history_entry(ticker, context, order, success, message):
    """Helper to save VA history."""
    hist_data = load_json(ConfigFile.VA_HISTORY, default=[])
    today = datetime.now(pytz.timezone('US/Eastern')).strftime("%Y-%m-%d")
    now_time = datetime.now(pytz.timezone('US/Eastern')).strftime("%H:%M:%S")

    # Find/Create Today Entry
    today_entry = next((item for item in hist_data if item["date"] == today), None)
    if not today_entry:
        today_entry = {"date": today, "targets": {}}
        hist_data.insert(0, today_entry)

    if ticker not in today_entry["targets"]:
        today_entry["targets"][ticker] = {
            "day_count": context.get("day_count", 0),
            "results": []
        }

    target_entry = today_entry["targets"][ticker]

    result_entry = {
        "time": now_time,
        "type": order.side.name if order else "skip",
        "qty": order.quantity if order else 0,
        "price": order.price if order else 0,
        "success": success,
        "message": message
    }
    target_entry["results"].append(result_entry)

    save_json(ConfigFile.VA_HISTORY, hist_data)

def _save_va_skips(context, orders):
    """Save 'skip' history for targets that had no orders."""
    order_tickers = {o.symbol for o in orders}
    for ticker, ctx in context.items():
        if ticker not in order_tickers and not ctx.get('already_executed'):
             _save_va_history_entry(ticker, ctx, None, True, "Skipped")

# -------------------------------------------------------------------------
# Rebalancing Execution
# -------------------------------------------------------------------------

def run_rebalancing_strategy(execute: bool = False) -> Dict[str, Any]:
    """
    Run Static Weight Rebalancing strategy cycle.
    """
    today_str = datetime.now(pytz.timezone('US/Eastern')).strftime("%Y-%m-%d")
    report = {
        "date": today_str,
        "status": "init",
        "orders": [],
        "execution_results": [],
        "info": {},
        "config": {},
        "error": None
    }

    try:
        # 1. Load Data (Scope: KIS only for rebalancing)
        portfolio_res = get_portfolio_data(scope="kis")
        holdings = portfolio_res.get('merged_data', {})

        # 2. Fetch Prices for Rebalancing Assets
        strategy_config = load_json(ConfigFile.STRATEGY_CONFIG, default={})
        reb_conf = strategy_config.get('rebalancing', {})
        report["config"] = reb_conf

        reb_assets = reb_conf.get('assets', [])
        prices = {}
        for a in reb_assets:
            t = a['ticker']
            # Try from portfolio first
            p = float(holdings.get(t, {}).get('cur_price', 0))
            if p <= 0:
                # If not held, fetch from API
                p = wrapper.fetch_price(t)
            prices[t] = p
            logging.info(f"Rebalancing: Price for {t} set to ${p}")

        if not reb_conf.get("enabled", False):
            report["status"] = "disabled"
            return report

        # 2. Check if already executed today (prevent duplicate LOC orders)
        if execute:
            hist_data = load_json(ConfigFile.REBALANCING_HISTORY, default=[])
            today_entry = next(
                (h for h in hist_data if h.get("date") == today_str and h.get("orders")),
                None
            )
            if today_entry:
                logging.info(f"Rebalancing: Already executed today at {today_entry.get('time', '?')}. Skipping.")
                report["status"] = "already_executed"
                report["info"] = {"message": f"Already executed at {today_entry.get('time', '?')}"}
                return report

        # 3. Calculate (Always calculate to show in report)
        orders, info = rebalancing.calculate_orders(
            config=reb_conf,
            portfolio=holdings,
            current_prices=prices
        )
        report["orders"] = orders
        report["info"] = info

        # 4. Check Status & Holiday
        is_holiday = is_market_holiday("NYSE", today_str)

        if is_holiday:
            report["status"] = "market_holiday"
        elif not orders:
            report["status"] = "no_orders"
        else:
            report["status"] = "calculated"
            # Log detailed status
            logging.info(f"Rebalancing: Calculated {len(orders)} orders for Seed ${info.get('seed')}")
            for ticker, status in info.get('asset_status', {}).items():
                logging.info(f"  [{ticker}] CurWeight: {status['cur_w']}% (Diff: {status['diff_w']}%p)")

        # 5. Execute (if requested and possible)
        # Only execute if status is 'calculated' (implies NOT holiday)
        if execute and report["status"] == "calculated":
            import time
            results = []

            # Separate Sells and Buys to ensure cash is secured first
            sell_orders = [o for o in orders if o.side == OrderSide.SELL]
            buy_orders = [o for o in orders if o.side == OrderSide.BUY]

            # Step A: Execute Sells First
            for order in sell_orders:
                success, msg = execute_single_order(order)
                results.append({"order": order, "success": success, "message": msg})

            # Step B: Wait for cash update (1 minute)
            if sell_orders and buy_orders:
                logging.info("Rebalancing: Sells executed. Waiting 60s for cash update...")
                time.sleep(60)

            # Step C: Execute Buys
            for order in buy_orders:
                success, msg = execute_single_order(order)
                results.append({"order": order, "success": success, "message": msg})

            report["execution_results"] = results
            success_count = sum(1 for r in results if r['success'])

            if success_count == len(orders):
                report["status"] = "executed"
            else:
                report["status"] = "partial_execution"

            # Save History
            _save_rebalancing_history(report)

    except Exception as e:
        logging.error(f"Rebalancing Service Error: {e}", exc_info=True)
        report["status"] = "error"
        report["error"] = str(e)

    return report

def _save_rebalancing_history(report: Dict):
    """Saves rebalancing execution details to JSON history."""
    if not report.get("execution_results") and report.get("status") != "no_orders":
        return

    hist_data = load_json(ConfigFile.REBALANCING_HISTORY, default=[])
    now = datetime.now(pytz.timezone('US/Eastern'))

    info = report.get("info", {})
    entry = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "seed": info.get("seed"),
        "usd_cash": info.get("usd_cash"),
        "total_available": info.get("total_available"),
        "scale_factor": info.get("scale_factor"),
        "assets": info.get("asset_status", {}),
        "orders": []
    }

    for res in report.get("execution_results", []):
        order = res["order"]
        entry["orders"].append({
            "ticker": order.symbol,
            "side": order.side.name,
            "qty": order.quantity,
            "price": order.price,
            "success": res["success"],
            "message": res["message"]
        })

    hist_data.insert(0, entry)
    save_json(ConfigFile.REBALANCING_HISTORY, hist_data[:200]) # Keep last 200 entries
