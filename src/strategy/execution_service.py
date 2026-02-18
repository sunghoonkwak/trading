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
from core import trading_config
from kis.kis_api.overseas_stock.order.order import order as order_overseas_stock
from data.data_service import get_portfolio_data

# -------------------------------------------------------------------------
# Common Helpers
# -------------------------------------------------------------------------

def _get_pending_buy_amount() -> float:
    """
    Fetch open orders from KIS and calculate total reserved USD for pending buys.
    This accounts for LOC orders that KIS doesn't deduct from available cash.
    """
    try:
        df, num_us, num_kr = wrapper.fetch_open_orders()
        if df.empty:
            logging.info("[PendingOrders] No open orders found")
            return 0.0

        total_reserved = 0.0
        for _, row in df.iterrows():
            row_l = {k.lower(): v for k, v in row.to_dict().items()}

            # Only US market buy orders
            if row_l.get('_market') != 'US':
                continue
            if row_l.get('sll_buy_dvsn_cd') != '02':  # 02 = Buy
                continue

            # Get price and quantity
            price = float(row_l.get('ft_ord_unpr3', 0) or row_l.get('ft_ord_unpr4', 0) or
                         row_l.get('ovrs_ord_unpr', 0) or row_l.get('ord_unpr', 0) or 0)
            qty = float(row_l.get('nccs_qty', 0) or row_l.get('ft_ord_qty4', 0) or
                       row_l.get('ord_qty', 0) or 0)

            if price > 0 and qty > 0:
                amount = price * qty
                ticker = row_l.get('pdno', 'N/A')
                logging.info(f"[PendingOrders] {ticker} BUY {int(qty)} @ ${price:.2f} = ${amount:.2f}")
                total_reserved += amount

        logging.info(f"[PendingOrders] Total reserved for pending buys: ${total_reserved:.2f}")
        return total_reserved

    except Exception as e:
        logging.error(f"[PendingOrders] Failed to fetch open orders: {e}")
        return 0.0


def _adjust_cash_for_pending_orders(holdings: Dict) -> Dict:
    """
    Adjust USD cash in holdings by subtracting pending buy order amounts.
    Returns a modified copy of holdings.
    """
    pending_amount = _get_pending_buy_amount()
    if pending_amount <= 0:
        return holdings

    adjusted = dict(holdings)
    if "USD cash" in adjusted:
        adjusted["USD cash"] = dict(adjusted["USD cash"])
        original_cash = float(adjusted["USD cash"].get("qty", 0))
        adjusted_cash = max(0, original_cash - pending_amount)
        adjusted["USD cash"]["qty"] = adjusted_cash
        logging.info(f"[PendingOrders] USD cash adjusted: ${original_cash:.2f} → ${adjusted_cash:.2f} (reserved: ${pending_amount:.2f})")

    return adjusted


def get_market_data(force_refresh: bool = False) -> Tuple[Dict, Dict]:
    """
    Fetch current portfolio and prices for all configured strategy targets.
    Returns: (portfolio_holdings, current_prices_map)
    """
    # 1. Portfolio
    portfolio = get_portfolio_data(force_refresh=force_refresh, scope="kis")
    holdings = portfolio.get('merged_data', {})

    # 1.5. Adjust cash for pending orders (KIS doesn't deduct LOC orders)
    if force_refresh:
        holdings = _adjust_cash_for_pending_orders(holdings)

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
        stock_info = trading_config.get_stock_info(order.symbol)
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

def _restore_orders_from_history(history_entry: Dict) -> List[Tuple[StrategyOrder, bool]]:
    """
    Restore orders from history with success status.

    Args:
        history_entry: History entry containing orders data

    Returns:
        List of tuples: (StrategyOrder, success_status)
    """
    orders_data = history_entry.get("orders", [])
    restored = []

    for order_data in orders_data:
        try:
            order = StrategyOrder(
                symbol=order_data["ticker"],
                side=OrderSide[order_data["side"]],
                quantity=order_data["qty"],
                price=order_data["price"],
                order_type=order_data["type"],
                reason=order_data.get("reason", "")
            )
            success = order_data.get("success", False)
            restored.append((order, success))
        except Exception as e:
            logging.error(f"Failed to restore order: {order_data}, error: {e}")
            continue

    return restored

def _update_raoeo_history(today_entry: Dict, new_results: List[Dict]):
    """
    Update today's history entry with re-execution results.

    Args:
        today_entry: The history entry for today
        new_results: List of execution results to update
    """
    hist_data = load_json(ConfigFile.RAOEO_HISTORY, default=[])
    today_date = today_entry.get("date")

    # Find today's entry and update
    for entry in hist_data:
        if entry.get("date") == today_date:
            # Update timestamp for re-execution
            entry["time"] = datetime.now(pytz.timezone('US/Eastern')).strftime("%H:%M:%S")

            for result in new_results:
                order = result["order"]
                # Find matching order and update status
                for hist_order in entry.get("orders", []):
                    if (hist_order["ticker"] == order.symbol and
                        hist_order["side"] == order.side.name and
                        hist_order["qty"] == order.quantity):
                        hist_order["success"] = result["success"]
                        hist_order["message"] = result["message"]
                        break
            break

    save_json(ConfigFile.RAOEO_HISTORY, hist_data)

def run_raoeo_strategy(execute: bool = False) -> Dict[str, Any]:
    """
    Run RAOEO strategy cycle.

    Args:
        execute: If True, executes the calculated orders (or re-executes failed ones).

    Returns:
        Dict containing report data:
        {
            "date": "YYYY-MM-DD",
            "status": "from_history" | "already_executed" | "partial_re_execution" |
                      "market_holiday" | "executed" | "calculated" | "error",
            "orders": [StrategyOrder objects...],
            "execution_results": [{"order": ..., "success": True, "message": ...}, ...],
            "holdings": {...},
            "config": {...},
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
        # 1. Check for today's history (always, regardless of execute flag)
        hist_data = load_json(ConfigFile.RAOEO_HISTORY, default=[])
        today_entry = next(
            (h for h in hist_data if h.get("date") == today_str and h.get("orders")),
            None
        )

        if today_entry:
            logging.info(f"RAOEO: Found today's history at {today_entry.get('time', '?')}. Restoring orders...")

            # Restore orders with success status
            orders_with_status = _restore_orders_from_history(today_entry)

            all_orders = [o for o, _ in orders_with_status]
            failed_orders = [o for o, success in orders_with_status if not success]

            report["orders"] = all_orders
            report["config"] = today_entry.get("config", {})

            if not execute:
                if not failed_orders:
                    # All succeeded - indicate already executed
                    report["status"] = "already_executed"
                    logging.info("RAOEO: All orders from history were successful.")
                else:
                    # Some failed - indicate from history (not re-executed)
                    report["status"] = "from_history"
                    logging.info(f"RAOEO: Returning {len(all_orders)} orders from history ({len(failed_orders)} failed).")
                return report

            # execute=True
            if not failed_orders:
                # All succeeded - no re-execution needed
                report["status"] = "already_executed"
                logging.info(f"RAOEO: All {len(all_orders)} orders already executed successfully.")
                return report
            else:
                # Re-execute only failed orders
                logging.info(f"RAOEO: Re-executing {len(failed_orders)} failed orders.")
                results = []
                success_count = 0

                for order in failed_orders:
                    success, msg = execute_single_order(order)
                    results.append({
                        "order": order,
                        "success": success,
                        "message": msg
                    })
                    if success: success_count += 1

                report["status"] = "partial_re_execution"
                report["execution_results"] = results

                # Update history with new results
                _update_raoeo_history(today_entry, results)

                logging.info(f"RAOEO: Re-executed {len(failed_orders)} orders, {success_count} succeeded.")
                return report

        # 2. No history - proceed with normal calculation

        # 2. Load Data
        holdings, prices = get_market_data(force_refresh=True)
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

            # Save History
            _save_raoeo_history(report)

    except Exception as e:
        logging.error(f"RAOEO Service Error: {e}", exc_info=True)
        report["status"] = "error"
        report["error"] = str(e)

    return report

def _save_raoeo_history(report: Dict):
    """Saves RAOEO execution details to JSON history."""
    # Only save if there were orders or it was a calculated/executed run
    if not report.get("orders") and report.get("status") not in ["executed", "calculated", "partial_execution"]:
        return

    hist_data = load_json(ConfigFile.RAOEO_HISTORY, default=[])
    now = datetime.now(pytz.timezone('US/Eastern'))

    # Create history entry
    entry = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "status": report.get("status"),
        "config": report.get("config", {}),
        "orders": []
    }

    # Add execution results if available
    if report.get("execution_results"):
        for res in report.get("execution_results", []):
            order = res["order"]
            entry["orders"].append({
                "ticker": order.symbol,
                "side": order.side.name,
                "qty": order.quantity,
                "price": order.price,
                "type": order.order_type,
                "reason": order.reason,
                "success": res["success"],
                "message": res["message"]
            })
    # If no execution results (e.g. calculation only), add calculated orders
    elif report.get("orders"):
         for order in report.get("orders", []):
            entry["orders"].append({
                "ticker": order.symbol,
                "side": order.side.name,
                "qty": order.quantity,
                "price": order.price,
                "type": order.order_type,
                "reason": order.reason,
                "success": False,
                "message": "Calculated Only"
            })

    hist_data.insert(0, entry)
    save_json(ConfigFile.RAOEO_HISTORY, hist_data[:200]) # Keep last 200 entries

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
        holdings, prices = get_market_data(force_refresh=True)

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

def _restore_rebalancing_execution_results(history_entry: Dict) -> List[Dict]:
    """Restore execution results from history entry for rebalancing."""
    results = []
    for o_data in history_entry.get("orders", []):
        try:
            order = StrategyOrder(
                symbol=o_data["ticker"],
                side=OrderSide[o_data["side"]],
                quantity=o_data["qty"],
                price=o_data["price"],
                order_type="00",
                reason=""
            )
            results.append({
                "order": order,
                "success": o_data.get("success", False),
                "message": o_data.get("message", "Restored from history")
            })
        except: continue
    return results

# -------------------------------------------------------------------------
# Rebalancing Execution
# -------------------------------------------------------------------------

def run_rebalancing_strategy(execute: bool = False) -> Dict[str, Any]:
    """
    Run Static Weight Rebalancing strategy cycle.
    """
    tz_et = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_et)
    today_str = now_et.strftime("%Y-%m-%d")
    
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
        # 1. Check for 'Already Executed' status FIRST
        hist_data = load_json(ConfigFile.REBALANCING_HISTORY, default=[])
        today_entry = next(
            (h for h in hist_data if str(h.get("date")).strip() == today_str and h.get("orders")),
            None
        )
        
        already_executed = False
        if today_entry:
            logging.info(f"[Rebalancing] Found execution record for {today_str}")
            already_executed = True
            report["status"] = "already_executed"
            report["execution_results"] = _restore_rebalancing_execution_results(today_entry)
            report["info"]["exec_time"] = today_entry.get("time")

        # 2. Load Data
        portfolio_res = get_portfolio_data(force_refresh=True, scope="kis")
        holdings = portfolio_res.get('merged_data', {})
        holdings = _adjust_cash_for_pending_orders(holdings)

        strategy_config = load_json(ConfigFile.STRATEGY_CONFIG, default={})
        reb_conf = strategy_config.get('rebalancing', {})
        report["config"] = reb_conf

        if not reb_conf.get("enabled", False):
            report["status"] = "disabled"
            return report

        reb_assets = reb_conf.get('assets', [])
        prices = {}
        for a in reb_assets:
            t = a['ticker']
            p = float(holdings.get(t, {}).get('cur_price', 0))
            if p <= 0:
                p = wrapper.fetch_price(t)
            prices[t] = p

        # 2.5. RAOEO Budget Reservation
        raoeo_conf = strategy_config.get('raoeo', {}).get('targets', {})
        raoeo_daily_total = 0.0
        for ticker, tcfg in raoeo_conf.items():
            r_seed = float(tcfg.get('seed', 0))
            r_duration = int(tcfg.get('duration', 1))
            if r_duration > 0 and r_seed > 0:
                raoeo_daily_total += r_seed / r_duration

        # 3. Calculate Orders
        orders, info = rebalancing.calculate_orders(
            config=reb_conf,
            portfolio=holdings,
            current_prices=prices,
            reserved_cash=raoeo_daily_total
        )
        report["orders"] = orders
        
        # Merge info into report["info"]
        for k, v in info.items():
            if k not in report["info"]:
                report["info"][k] = v

        # 4. Final Status Determination
        is_holiday = is_market_holiday("NYSE", today_str)

        if is_holiday:
            report["status"] = "market_holiday"
        elif already_executed:
            report["status"] = "already_executed"
        elif not orders:
            report["status"] = "no_orders"
        else:
            report["status"] = "calculated"

        # 5. Execute phase (Guarded)
        if execute and report["status"] == "calculated" and not already_executed:
            import time
            results = []
            sell_orders = [o for o in orders if o.side == OrderSide.SELL]
            buy_orders = [o for o in orders if o.side == OrderSide.BUY]

            for order in sell_orders:
                success, msg = execute_single_order(order)
                results.append({"order": order, "success": success, "message": msg})

            if sell_orders and buy_orders:
                logging.info("[Rebalancing] Sells done. Waiting 60s for cash update...")
                time.sleep(60)

            for order in buy_orders:
                success, msg = execute_single_order(order)
                results.append({"order": order, "success": success, "message": msg})

            report["execution_results"] = results
            success_count = sum(1 for r in results if r['success'])
            report["status"] = "executed" if success_count == len(orders) else "partial_execution"
            
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
