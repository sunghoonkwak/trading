# -*- coding: utf-8 -*-
"""
Strategy Execution Service (Centralized)

This module handles the orchestration of strategy execution:
1. Unified 6-step flow for all strategies
2. Centralized market status & history management
3. Single integrated history file (strategy_history.json)
"""
import logging
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any

import pytz
import requests

from strategy import raoeo, value_averaging, rebalancing
from strategy.base import StrategyOrder, StrategyStatus, OrderSide
from data.config_manager import ConfigFile, load_json, save_json
from utils.market_utils import get_us_market_status, is_market_holiday
from kis import wrapper
from kis.kis_api import kis_auth as ka
from core import trading_config
from kis.kis_api.overseas_stock.order.order import order as order_overseas_stock
from data.data_service import get_portfolio_data

# Timezone constant
TZ_ET = pytz.timezone('US/Eastern')


# -------------------------------------------------------------------------
# Common Helpers
# -------------------------------------------------------------------------

def get_market_data(force_refresh: bool = False) -> Tuple[Dict, Dict]:
    """
    Fetch current portfolio and prices for all configured strategy targets.
    Returns: (portfolio_holdings, current_prices_map)
    """
    portfolio = get_portfolio_data(force_refresh=force_refresh, scope="kis")
    holdings = portfolio.get('merged_data', {})

    strategy_config = load_json(ConfigFile.STRATEGY_CONFIG, default={})
    raoeo_conf = strategy_config.get('raoeo', {}).get('targets', {})
    va_conf = strategy_config.get('value_averaging', {}).get('targets', {})
    reb_conf = strategy_config.get('rebalancing', {}).get('assets', [])

    reb_tickers = {a['ticker'] for a in reb_conf}
    all_tickers = set(raoeo_conf.keys()) | set(va_conf.keys()) | reb_tickers
    current_prices = {}

    for t in all_tickers:
        price = wrapper.fetch_price(t)
        if price > 0:
            current_prices[t] = price
        else:
            if t in holdings:
                current_prices[t] = float(holdings[t].get('cur_price', 0))

    return holdings, current_prices


def execute_single_order(order: StrategyOrder) -> Tuple[bool, str]:
    """Execute a single strategy order via KIS API."""
    try:
        cano = ka.getTREnv().my_acct
        acnt_prdt_cd = ka.getTREnv().my_prod

        ord_dv = "buy" if order.side == OrderSide.BUY else "sell"

        exec_price = order.price
        exec_type = order.order_type
        if order.side == OrderSide.SELL and order.price == 0:
            exec_price = 0.01
            exec_type = "00"

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
    except requests.exceptions.Timeout:
        error_msg = f"[API Timeout] execution timed out for {order.symbol}"
        logging.error(error_msg)
        return False, error_msg
    except Exception as e:
        return False, str(e)


def _get_market_status(today_str: str) -> Dict:
    """
    Centralized market status determination.
    Returns: { "is_market_open": bool, "is_holiday": bool, "message": str }
    """
    is_holiday = is_market_holiday("NYSE", today_str)
    if is_holiday:
        return {"is_market_open": False, "is_holiday": True, "message": "Market closed (Holiday)"}

    is_allowed, market_msg = get_us_market_status()
    return {"is_market_open": is_allowed, "is_holiday": False, "message": market_msg}


def _build_base_report(today_str: str, market_status: Dict) -> Dict:
    """Create base report structure used by all strategies."""
    return {
        "date": today_str,
        "status": None,
        "market_status": market_status,
        "orders": [],
        "succeeded_orders": [],
        "pending_orders": [],
        "execution_results": [],
        "info": {},
        "error": None,
    }


# -------------------------------------------------------------------------
# Unified History Management
# -------------------------------------------------------------------------

def _load_history() -> list:
    """Load unified strategy history."""
    return load_json(ConfigFile.STRATEGY_HISTORY, default=[])


def _get_today_entry(hist_data: list, today_str: str) -> Dict:
    """Find or create today's entry in history."""
    for entry in hist_data:
        if entry.get("date") == today_str:
            return entry
    return None


def _restore_orders_from_strategy_history(
    strategy_data: Dict
) -> List[Tuple[StrategyOrder, bool]]:
    """
    Restore orders from a strategy's history section with success status.
    Returns: List of (StrategyOrder, success_status) tuples
    """
    orders_data = strategy_data.get("orders", [])
    restored = []

    for order_data in orders_data:
        try:
            order = StrategyOrder(
                symbol=order_data["ticker"],
                side=OrderSide[order_data["side"]],
                quantity=order_data["qty"],
                price=order_data["price"],
                order_type=order_data.get("order_type", "00"),
                reason=order_data.get("reason", "")
            )
            success = order_data.get("success", False)
            restored.append((order, success))
        except Exception as e:
            logging.error(f"Failed to restore order: {order_data}, error: {e}")
            continue

    return restored


def _save_strategy_to_history(
    today_str: str,
    strategy_key: str,
    strategy_data: Dict
):
    """Save a strategy's result to the unified history file."""
    hist_data = _load_history()

    # Find or create today's entry
    today_entry = _get_today_entry(hist_data, today_str)
    if not today_entry:
        today_entry = {"date": today_str}
        hist_data.insert(0, today_entry)

    # Update strategy section
    today_entry[strategy_key] = strategy_data

    # Keep last 200 entries
    save_json(ConfigFile.STRATEGY_HISTORY, hist_data[:200])


def _build_strategy_history_data(
    report: Dict,
    strategy_key: str,
    extra_fields: Dict = None
) -> Dict:
    """Build the history data dict for a strategy from its report."""
    now_et = datetime.now(TZ_ET)
    data = {
        "time": now_et.strftime("%H:%M:%S"),
        "status": report["status"].value if isinstance(report["status"], StrategyStatus) else report["status"],
        "orders": [],
    }

    # Add extra fields (e.g., targets_context for VA, context for Rebalancing)
    if extra_fields:
        data.update(extra_fields)

    # Build order list from execution results or calculated orders
    if report.get("execution_results"):
        for res in report["execution_results"]:
            order = res["order"]
            data["orders"].append({
                "ticker": order.symbol,
                "side": order.side.name,
                "qty": order.quantity,
                "price": order.price,
                "order_type": order.order_type,
                "reason": order.reason,
                "success": res["success"],
                "message": res["message"],
            })
    elif report.get("orders"):
        for order in report["orders"]:
            data["orders"].append({
                "ticker": order.symbol,
                "side": order.side.name,
                "qty": order.quantity,
                "price": order.price,
                "order_type": order.order_type,
                "reason": order.reason,
                "success": False,
                "message": "Calculated Only",
            })

    return data


def _execute_orders(
    orders: List[StrategyOrder],
    sell_first: bool = False,
    sell_wait_seconds: int = 0,
) -> List[Dict]:
    """
    Execute a list of orders. Optionally execute sells first with a wait.
    Returns: list of execution result dicts
    """
    results = []

    if sell_first:
        sell_orders = [o for o in orders if o.side == OrderSide.SELL]
        buy_orders = [o for o in orders if o.side == OrderSide.BUY]

        for order in sell_orders:
            success, msg = execute_single_order(order)
            results.append({"order": order, "success": success, "message": msg})

        if sell_orders and buy_orders and sell_wait_seconds > 0:
            logging.info(f"Sells done. Waiting {sell_wait_seconds}s for cash update...")
            time.sleep(sell_wait_seconds)

        for order in buy_orders:
            success, msg = execute_single_order(order)
            results.append({"order": order, "success": success, "message": msg})
    else:
        for order in orders:
            success, msg = execute_single_order(order)
            results.append({"order": order, "success": success, "message": msg})

    return results


# -------------------------------------------------------------------------
# RAOEO Execution
# -------------------------------------------------------------------------

def run_raoeo_strategy(execute: bool = False) -> Dict[str, Any]:
    """
    Run RAOEO strategy with unified 6-step flow.
    """
    today_str = datetime.now(TZ_ET).strftime("%Y-%m-%d")
    market_status = _get_market_status(today_str)
    report = _build_base_report(today_str, market_status)

    try:
        # Step 1: Check enabled
        strategy_config = load_json(ConfigFile.STRATEGY_CONFIG, default={})
        raoeo_section = strategy_config.get('raoeo', {})

        if not raoeo_section.get('enabled', True):
            report["status"] = StrategyStatus.DISABLED
            return report

        raoeo_conf = raoeo_section.get('targets', {})

        # Filter enabled tickers only
        active_targets = {
            t: c for t, c in raoeo_conf.items() if c.get('enabled', True)
        }

        if not active_targets:
            report["status"] = StrategyStatus.DISABLED
            return report

        # Step 2: Market status (already determined above)

        # Step 3: Check today's history
        hist_data = _load_history()
        today_entry = _get_today_entry(hist_data, today_str)
        raoeo_hist = today_entry.get("raoeo") if today_entry else None

        if raoeo_hist and raoeo_hist.get("orders"):
            # Step 4: History exists — separate succeeded/pending
            logging.info(f"RAOEO: Found today's history at {raoeo_hist.get('time', '?')}")
            orders_with_status = _restore_orders_from_strategy_history(raoeo_hist)

            all_orders = [o for o, _ in orders_with_status]
            succeeded = [o for o, s in orders_with_status if s]
            failed = [o for o, s in orders_with_status if not s]

            report["orders"] = all_orders
            report["succeeded_orders"] = succeeded
            report["pending_orders"] = failed

            if not failed:
                report["status"] = StrategyStatus.EXECUTED
                logging.info("RAOEO: All orders from history were successful.")

                if not execute:
                    return report
                # execute=True but all done
                return report
            else:
                if not execute:
                    report["status"] = StrategyStatus.PARTIAL
                    return report

                # Re-execute failed orders
                if not market_status["is_market_open"]:
                    report["status"] = StrategyStatus.NON_MARKET_TIME
                    return report

                logging.info(f"RAOEO: Re-executing {len(failed)} failed orders.")
                results = _execute_orders(failed, sell_first=True, sell_wait_seconds=5)
                report["execution_results"] = results

                success_count = sum(1 for r in results if r['success'])
                report["status"] = StrategyStatus.EXECUTED if success_count == len(failed) else StrategyStatus.PARTIAL

                # Update history
                hist_entry_data = _build_strategy_history_data(report, "raoeo")
                # Merge: keep succeeded, update failed
                merged_orders = []
                for o in succeeded:
                    merged_orders.append({
                        "ticker": o.symbol, "side": o.side.name,
                        "qty": o.quantity, "price": o.price,
                        "order_type": o.order_type, "reason": o.reason,
                        "success": True, "message": "Success",
                    })
                for res in results:
                    o = res["order"]
                    merged_orders.append({
                        "ticker": o.symbol, "side": o.side.name,
                        "qty": o.quantity, "price": o.price,
                        "order_type": o.order_type, "reason": o.reason,
                        "success": res["success"], "message": res["message"],
                    })
                hist_entry_data["orders"] = merged_orders
                _save_strategy_to_history(today_str, "raoeo", hist_entry_data)

                return report

        # Step 5: No history — calculate
        if market_status["is_holiday"]:
            report["status"] = StrategyStatus.HOLIDAY
            return report

        holdings, prices = get_market_data(force_refresh=True)
        report["info"]["holdings"] = holdings

        orders, calc_info = raoeo.calculate_orders(
            targets_config=active_targets,
            portfolio=holdings,
            current_prices=prices,
            cash_ticker=strategy_config.get("cash_ticker", "")
        )
        report["orders"] = orders
        report["pending_orders"] = orders
        report["info"].update(calc_info)

        if not orders:
            report["status"] = StrategyStatus.SKIPPED
            return report

        # Step 6: Execute if requested
        if not execute:
            if not market_status["is_market_open"]:
                report["status"] = StrategyStatus.NON_MARKET_TIME
            else:
                report["status"] = StrategyStatus.SKIPPED
            return report

        if not market_status["is_market_open"]:
            report["status"] = StrategyStatus.NON_MARKET_TIME
            return report

        results = _execute_orders(orders, sell_first=True, sell_wait_seconds=5)
        report["execution_results"] = results

        success_count = sum(1 for r in results if r['success'])
        report["status"] = StrategyStatus.EXECUTED if success_count == len(orders) else StrategyStatus.PARTIAL

        # Update succeeded/pending based on results
        report["succeeded_orders"] = [r["order"] for r in results if r["success"]]
        report["pending_orders"] = [r["order"] for r in results if not r["success"]]

        # Save history
        hist_data = _build_strategy_history_data(report, "raoeo")
        _save_strategy_to_history(today_str, "raoeo", hist_data)

    except requests.exceptions.Timeout as e:
        logging.error(f"[API Timeout] RAOEO Service Timeout Error: {e}", exc_info=True)
        report["status"] = StrategyStatus.ERROR
        report["error"] = "API Timeout"
    except Exception as e:
        logging.error(f"RAOEO Service Error: {e}", exc_info=True)
        report["status"] = StrategyStatus.ERROR
        report["error"] = str(e)

    return report


# -------------------------------------------------------------------------
# Value Averaging Execution
# -------------------------------------------------------------------------

def run_va_strategy(execute: bool = False) -> Dict[str, Any]:
    """
    Run Value Averaging strategy with unified 6-step flow.
    """
    today_str = datetime.now(TZ_ET).strftime("%Y-%m-%d")
    market_status = _get_market_status(today_str)
    report = _build_base_report(today_str, market_status)

    try:
        # Step 1: Check enabled
        strategy_config = load_json(ConfigFile.STRATEGY_CONFIG, default={})
        va_section = strategy_config.get('value_averaging', {})

        if not va_section.get('enabled', True):
            report["status"] = StrategyStatus.DISABLED
            return report

        va_conf = va_section.get('targets', {})

        if not va_conf:
            report["status"] = StrategyStatus.DISABLED
            return report

        # Step 2: Market status (already determined)

        # Step 3: Check today's history
        hist_data = _load_history()
        today_entry = _get_today_entry(hist_data, today_str)
        va_hist = today_entry.get("va") if today_entry else None

        if va_hist and va_hist.get("orders"):
            # Step 4: History exists
            logging.info(f"VA: Found today's history at {va_hist.get('time', '?')}")
            orders_with_status = _restore_orders_from_strategy_history(va_hist)

            all_orders = [o for o, _ in orders_with_status]
            succeeded = [o for o, s in orders_with_status if s]
            failed = [o for o, s in orders_with_status if not s]

            report["orders"] = all_orders
            report["succeeded_orders"] = succeeded
            report["pending_orders"] = failed

            # Restore targets_context
            report["info"]["targets_context"] = va_hist.get("targets_context", {})

            if not failed:
                report["status"] = StrategyStatus.EXECUTED
                return report
            else:
                if not execute:
                    report["status"] = StrategyStatus.PARTIAL
                    return report

                if not market_status["is_market_open"]:
                    report["status"] = StrategyStatus.NON_MARKET_TIME
                    return report

                results = _execute_orders(failed)
                report["execution_results"] = results

                success_count = sum(1 for r in results if r['success'])
                report["status"] = StrategyStatus.EXECUTED if success_count == len(failed) else StrategyStatus.PARTIAL

                # Update history with merged results
                merged_orders = []
                for o in succeeded:
                    merged_orders.append({
                        "ticker": o.symbol, "side": o.side.name,
                        "qty": o.quantity, "price": o.price,
                        "order_type": o.order_type, "reason": o.reason,
                        "success": True, "message": "Success",
                    })
                for res in results:
                    o = res["order"]
                    merged_orders.append({
                        "ticker": o.symbol, "side": o.side.name,
                        "qty": o.quantity, "price": o.price,
                        "order_type": o.order_type, "reason": o.reason,
                        "success": res["success"], "message": res["message"],
                    })

                save_data = _build_strategy_history_data(report, "va",
                    extra_fields={"targets_context": va_hist.get("targets_context", {})})
                save_data["orders"] = merged_orders
                _save_strategy_to_history(today_str, "va", save_data)

                return report

        # Step 5: No history — calculate
        if market_status["is_holiday"]:
            report["status"] = StrategyStatus.HOLIDAY
            return report

        holdings, prices = get_market_data(force_refresh=True)

        # VA needs history for day_count calculation
        orders, context_map = value_averaging.calculate_orders(
            targets_config=va_conf,
            portfolio=holdings,
            current_prices=prices,
            history_data=hist_data,
            today_date=today_str
        )

        report["orders"] = orders
        report["pending_orders"] = orders
        report["info"]["targets_context"] = {
            t: {"day_count": ctx.get("day_count", 0)} for t, ctx in context_map.items()
        }
        report["info"]["context_map"] = context_map

        if not orders:
            report["status"] = StrategyStatus.SKIPPED
        elif not execute:
            report["status"] = StrategyStatus.NON_MARKET_TIME if not market_status["is_market_open"] else StrategyStatus.SKIPPED
        elif not market_status["is_market_open"]:
            report["status"] = StrategyStatus.NON_MARKET_TIME
        else:
            # Execute
            results = _execute_orders(orders)
            report["execution_results"] = results

            success_count = sum(1 for r in results if r['success'])
            report["status"] = StrategyStatus.EXECUTED if success_count == len(orders) else StrategyStatus.PARTIAL
            report["succeeded_orders"] = [r["order"] for r in results if r["success"]]
            report["pending_orders"] = [r["order"] for r in results if not r["success"]]

        # Save history (always save for VA — day_count tracking)
        targets_context = {
            t: {"day_count": ctx.get("day_count", 0)} for t, ctx in context_map.items()
        }
        save_data = _build_strategy_history_data(report, "va",
            extra_fields={"targets_context": targets_context})
        _save_strategy_to_history(today_str, "va", save_data)

    except requests.exceptions.Timeout as e:
        logging.error(f"[API Timeout] VA Service Timeout Error: {e}", exc_info=True)
        report["status"] = StrategyStatus.ERROR
        report["error"] = "API Timeout"
    except Exception as e:
        logging.error(f"VA Service Error: {e}", exc_info=True)
        report["status"] = StrategyStatus.ERROR
        report["error"] = str(e)

    return report


# -------------------------------------------------------------------------
# Rebalancing Execution
# -------------------------------------------------------------------------

def run_rebalancing_strategy(execute: bool = False) -> Dict[str, Any]:
    """
    Run Rebalancing strategy with unified 6-step flow.
    """
    today_str = datetime.now(TZ_ET).strftime("%Y-%m-%d")
    market_status = _get_market_status(today_str)
    report = _build_base_report(today_str, market_status)

    try:
        # Step 1: Check enabled
        strategy_config = load_json(ConfigFile.STRATEGY_CONFIG, default={})
        reb_conf = strategy_config.get('rebalancing', {})

        if not reb_conf.get('enabled', False):
            report["status"] = StrategyStatus.DISABLED
            return report

        # Step 2: Market status (already determined)

        # Step 3: Check today's history
        hist_data = _load_history()
        today_entry = _get_today_entry(hist_data, today_str)
        reb_hist = today_entry.get("rebalancing") if today_entry else None

        if reb_hist and reb_hist.get("orders"):
            # Step 4: History exists
            logging.info(f"[Rebalancing] Found today's history at {reb_hist.get('time', '?')}")
            orders_with_status = _restore_orders_from_strategy_history(reb_hist)

            all_orders = [o for o, _ in orders_with_status]
            succeeded = [o for o, s in orders_with_status if s]
            failed = [o for o, s in orders_with_status if not s]

            report["orders"] = all_orders
            report["succeeded_orders"] = succeeded
            report["pending_orders"] = failed
            report["info"]["context"] = reb_hist.get("context", {})

            if not failed:
                report["status"] = StrategyStatus.ALREADY_DONE
            else:
                report["status"] = StrategyStatus.PARTIAL

            # Rebalancing doesn't re-execute — always return as-is
            return report

        # Step 5: No history — calculate
        if market_status["is_holiday"]:
            report["status"] = StrategyStatus.HOLIDAY
            return report

        # Load market data (portfolio + prices)
        holdings, prices = get_market_data(force_refresh=True)

        # RAOEO budget reservation
        raoeo_conf = strategy_config.get('raoeo', {}).get('targets', {})
        raoeo_daily_total = 0.0
        for ticker, tcfg in raoeo_conf.items():
            if not tcfg.get('enabled', True):
                continue
            r_seed = float(tcfg.get('seed', 0))
            r_duration = int(tcfg.get('duration', 1))
            if r_duration > 0 and r_seed > 0:
                raoeo_daily_total += r_seed / r_duration

        # Calculate
        orders, calc_info = rebalancing.calculate_orders(
            config=reb_conf,
            portfolio=holdings,
            current_prices=prices,
            reserved_cash=raoeo_daily_total
        )

        report["orders"] = orders
        report["pending_orders"] = orders
        report["info"].update(calc_info)

        if not orders:
            report["status"] = StrategyStatus.SKIPPED
            return report

        # Step 6: Execute if requested
        if not execute:
            report["status"] = StrategyStatus.NON_MARKET_TIME if not market_status["is_market_open"] else StrategyStatus.SKIPPED
            return report

        if not market_status["is_market_open"]:
            report["status"] = StrategyStatus.NON_MARKET_TIME
            return report

        results = _execute_orders(orders, sell_first=True, sell_wait_seconds=60)
        report["execution_results"] = results

        success_count = sum(1 for r in results if r['success'])
        report["status"] = StrategyStatus.EXECUTED if success_count == len(orders) else StrategyStatus.PARTIAL
        report["succeeded_orders"] = [r["order"] for r in results if r["success"]]
        report["pending_orders"] = [r["order"] for r in results if not r["success"]]

        # Save history
        context = {
            "seed": calc_info.get("seed"),
            "usd_cash": calc_info.get("usd_cash"),
            "total_available": calc_info.get("total_available"),
            "scale_factor": calc_info.get("scale_factor"),
            "asset_status": calc_info.get("asset_status", {}),
        }
        save_data = _build_strategy_history_data(report, "rebalancing",
            extra_fields={"context": context})
        _save_strategy_to_history(today_str, "rebalancing", save_data)

    except requests.exceptions.Timeout as e:
        logging.error(f"[API Timeout] Rebalancing Service Timeout Error: {e}", exc_info=True)
        report["status"] = StrategyStatus.ERROR
        report["error"] = "API Timeout"
    except Exception as e:
        logging.error(f"Rebalancing Service Error: {e}", exc_info=True)
        report["status"] = StrategyStatus.ERROR
        report["error"] = str(e)

    return report
