# -*- coding: utf-8 -*-
"""
Strategy Execution Service (Centralized)

This module handles the orchestration of strategy execution:
1. Unified 6-step flow for all strategies
2. Centralized market status & history management
3. Single integrated history file (strategy_history.json)
"""
import logging
import requests
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any

import pytz

from broker import market_data, strategy_broker
from strategy import raoeo, value_averaging, rebalancing
from strategy.base import StrategyOrder, StrategyStatus, OrderSide
from strategy.constants import ORDER_TYPE_LIMIT
from data.config_manager import ConfigFile, load_json, save_json
from utils.market_utils import get_us_market_status, is_market_holiday
from utils.price_utils import resolve_current_price

# Timezone constant
TZ_ET = pytz.timezone('US/Eastern')
_orderable_usd_cache: Dict[str, float] = {}


# -------------------------------------------------------------------------
# Common Helpers
# -------------------------------------------------------------------------

def get_market_data(
    force_refresh: bool = False,
    include_cash_ticker: bool = False,
) -> Tuple[Dict, Dict]:
    """
    Fetch current portfolio and prices for all configured strategy targets.
    Returns: (portfolio_holdings, current_prices_map)
    """
    from data.data_service import get_portfolio_data

    portfolio = get_portfolio_data(force_refresh=force_refresh, scope="strategy")
    holdings = portfolio.get('merged_data', {})

    strategy_config = load_json(ConfigFile.STRATEGY_CONFIG, default={})
    raoeo_conf = strategy_config.get('raoeo', {}).get('targets', {})
    va_conf = strategy_config.get('value_averaging', {}).get('targets', {})
    reb_conf = strategy_config.get('rebalancing', {}).get('assets', [])
    cash_ticker = strategy_config.get("cash_ticker", "")

    reb_tickers = {a['ticker'] for a in reb_conf}
    all_tickers = set(raoeo_conf.keys()) | set(va_conf.keys()) | reb_tickers
    if include_cash_ticker and cash_ticker:
        all_tickers.add(cash_ticker)
    current_prices = {}

    for t in all_tickers:
        price = resolve_current_price(
            t,
            holdings.get(t, {}),
            {t: market_data.fetch_price(t)},
        )
        if price > 0:
            current_prices[t] = price

    return holdings, current_prices


def get_orderable_usd(symbol: str, order_price: float) -> float:
    """Return strategy-broker USD buying power for a representative buy."""
    return strategy_broker.get_orderable_usd(symbol, order_price)


def _get_rebalancing_orderable_usd(
    symbol: str,
    order_price: float,
    cache_key: str = "",
) -> float:
    """Reuse buying power during one automatic trading-day check cycle."""
    if not cache_key:
        return get_orderable_usd(symbol, order_price)
    if cache_key not in _orderable_usd_cache:
        _orderable_usd_cache.clear()
        _orderable_usd_cache[cache_key] = get_orderable_usd(symbol, order_price)
    return _orderable_usd_cache[cache_key]


def execute_single_order(order: StrategyOrder) -> Tuple[bool, str]:
    """Execute a single strategy order via the configured strategy broker."""
    return strategy_broker.place_order(order)


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
                order_type=order_data.get("order_type", ORDER_TYPE_LIMIT),
                reason=order_data.get("reason", ""),
                target_budget=order_data.get("target_budget"),
            )
            success = order_data.get("success", False)
            restored.append((order, success))
        except Exception as e:
            logging.error(f"Failed to restore order: {order_data}, error: {e}")
            continue

    return restored


def _build_order_history_entry(order: StrategyOrder, success: bool, message: str) -> Dict:
    """Serialize a strategy order for strategy_history.json."""
    entry = {
        "ticker": order.symbol,
        "side": order.side.name,
        "qty": order.quantity,
        "price": order.price,
        "order_type": order.order_type,
        "reason": order.reason,
        "success": success,
        "message": message,
    }
    if order.target_budget is not None:
        entry["target_budget"] = order.target_budget
    return entry


def _restore_history_orders(report: Dict, strategy_hist: Dict) -> Tuple[List[StrategyOrder], List[StrategyOrder]]:
    """Restore historical orders into a report and return succeeded/failed lists."""
    orders_with_status = _restore_orders_from_strategy_history(strategy_hist)
    all_orders = [order for order, _ in orders_with_status]
    succeeded = [order for order, success in orders_with_status if success]
    failed = [order for order, success in orders_with_status if not success]

    report["orders"] = all_orders
    report["succeeded_orders"] = succeeded
    report["pending_orders"] = failed
    return succeeded, failed


def _apply_execution_results(
    report: Dict,
    orders: List[StrategyOrder],
    results: List[Dict],
) -> None:
    """Store execution results and derive report status/order buckets."""
    report["execution_results"] = results
    report["status"] = _execution_status(orders, results)
    report["succeeded_orders"] = [
        result["order"] for result in results if result["success"]
    ]
    report["pending_orders"] = [
        result["order"] for result in results if not result["success"]
    ]


def _execution_status(
    orders: List[StrategyOrder],
    results: List[Dict],
) -> StrategyStatus:
    success_count = sum(1 for result in results if result["success"])
    if success_count == len(orders):
        return StrategyStatus.EXECUTED
    return StrategyStatus.PARTIAL


def _build_merged_history_entries(
    succeeded: List[StrategyOrder],
    results: List[Dict],
) -> List[Dict]:
    """Merge previous successes with the latest retry results for history."""
    merged_orders = [
        _build_order_history_entry(order, True, "Success")
        for order in succeeded
    ]
    for result in results:
        order = result["order"]
        merged_orders.append(_build_order_history_entry(
            order,
            result["success"],
            result["message"],
        ))
    return merged_orders


def _retry_failed_history_orders(
    report: Dict,
    strategy_key: str,
    today_str: str,
    succeeded: List[StrategyOrder],
    failed: List[StrategyOrder],
    extra_fields: Dict = None,
    sell_first: bool = False,
    sell_wait_seconds: int = 0,
) -> None:
    results = _execute_orders(
        failed,
        sell_first=sell_first,
        sell_wait_seconds=sell_wait_seconds,
    )
    report["execution_results"] = results
    report["status"] = _execution_status(failed, results)

    save_data = _build_strategy_history_data(
        report,
        strategy_key,
        extra_fields=extra_fields,
    )
    save_data["orders"] = _build_merged_history_entries(succeeded, results)
    _save_strategy_to_history(today_str, strategy_key, save_data)


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
    previous_data = today_entry.get(strategy_key, {})
    if strategy_key == "raoeo" and previous_data.get("cash_funding_results"):
        strategy_data.setdefault(
            "cash_funding_results",
            previous_data["cash_funding_results"],
        )
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

    if strategy_key == "raoeo":
        skipped_buy_budgets = report.get("info", {}).get("skipped_buy_budgets")
        if skipped_buy_budgets:
            data["skipped_buy_budgets"] = skipped_buy_budgets

    # Build order list from execution results or calculated orders
    if report.get("execution_results"):
        for res in report["execution_results"]:
            order = res["order"]
            data["orders"].append(_build_order_history_entry(
                order,
                res["success"],
                res["message"],
            ))
    elif report.get("orders"):
        for order in report["orders"]:
            data["orders"].append(_build_order_history_entry(
                order,
                False,
                "Calculated Only",
            ))

    return data


def prepare_raoeo_cash_funding(raoeo_report: Dict = None) -> Tuple[Any, Dict]:
    """Calculate a manual cash-ticker funding order for pending RAOEO buys."""
    if raoeo_report is None:
        raoeo_report = run_raoeo_strategy(execute=False)

    pending_orders = raoeo_report.get("pending_orders", [])
    reference_buy = next(
        (order for order in pending_orders if order.side == OrderSide.BUY),
        None,
    )
    orderable_usd = (
        get_orderable_usd(reference_buy.symbol, reference_buy.price)
        if reference_buy
        else 0.0
    )
    strategy_config = load_json(ConfigFile.STRATEGY_CONFIG, default={})
    holdings, prices = get_market_data(
        force_refresh=True,
        include_cash_ticker=True,
    )
    return raoeo.calculate_cash_funding_order(
        orders=pending_orders,
        portfolio=holdings,
        current_prices=prices,
        cash_ticker=strategy_config.get("cash_ticker", ""),
        orderable_usd=orderable_usd,
    )


def execute_raoeo_cash_funding(raoeo_report: Dict = None) -> Tuple[Any, Dict]:
    """Execute approved funding first; callers must stop if it fails."""
    order, info = prepare_raoeo_cash_funding(raoeo_report)
    if not info.get("required"):
        return None, info
    if order is None:
        return None, info

    success, message = execute_single_order(order)
    result = {"order": order, "success": success, "message": message}
    if success:
        logging.info("Cash funding sale accepted. Waiting 5s before strategy execution...")
        time.sleep(5)
    return result, info


def save_raoeo_cash_funding_result(today_str: str, result: Dict) -> List[Dict]:
    """Store a manual funding result without turning it into a retry order."""
    order = result.get("order") if result else None
    if order is None:
        return []

    hist_data = _load_history()
    today_entry = _get_today_entry(hist_data, today_str)
    if not today_entry:
        today_entry = {"date": today_str}
        hist_data.insert(0, today_entry)

    raoeo_data = today_entry.setdefault("raoeo", {"orders": []})
    results = raoeo_data.setdefault("cash_funding_results", [])
    results.append({
        "ticker": order.symbol,
        "side": order.side.name,
        "qty": order.quantity,
        "price": order.price,
        "order_type": order.order_type,
        "reason": order.reason,
        "success": result["success"],
        "message": result["message"],
    })
    save_json(ConfigFile.STRATEGY_HISTORY, hist_data[:200])
    return results


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


def _handle_raoeo_history(
    report: Dict,
    raoeo_hist: Dict,
    execute: bool,
    market_status: Dict,
    today_str: str,
) -> None:
    logging.info(f"RAOEO: Found today's history at {raoeo_hist.get('time', '?')}")
    succeeded, failed = _restore_history_orders(report, raoeo_hist)

    if not failed:
        report["status"] = StrategyStatus.EXECUTED
        logging.info("RAOEO: All orders from history were successful.")
        return

    if not execute:
        report["status"] = StrategyStatus.PARTIAL
        return

    if not market_status["is_market_open"]:
        report["status"] = StrategyStatus.NON_MARKET_TIME
        return

    logging.info(f"RAOEO: Re-executing {len(failed)} failed orders.")
    _retry_failed_history_orders(
        report,
        "raoeo",
        today_str,
        succeeded,
        failed,
        sell_first=True,
        sell_wait_seconds=5,
    )


def _handle_va_history(
    report: Dict,
    va_hist: Dict,
    execute: bool,
    market_status: Dict,
    today_str: str,
) -> None:
    logging.info(f"VA: Found today's history at {va_hist.get('time', '?')}")
    succeeded, failed = _restore_history_orders(report, va_hist)
    report["info"]["targets_context"] = va_hist.get("targets_context", {})

    if not failed:
        report["status"] = StrategyStatus.EXECUTED
        return

    if not execute:
        report["status"] = StrategyStatus.PARTIAL
        return

    if not market_status["is_market_open"]:
        report["status"] = StrategyStatus.NON_MARKET_TIME
        return

    _retry_failed_history_orders(
        report,
        "va",
        today_str,
        succeeded,
        failed,
        extra_fields={
            "targets_context": va_hist.get("targets_context", {}),
        },
    )


def _handle_rebalancing_history(report: Dict, reb_hist: Dict) -> None:
    logging.info(f"[Rebalancing] Found today's history at {reb_hist.get('time', '?')}")
    _, failed = _restore_history_orders(report, reb_hist)
    report["info"]["context"] = reb_hist.get("context", {})

    if not failed:
        report["status"] = StrategyStatus.ALREADY_DONE
    else:
        report["status"] = StrategyStatus.PARTIAL


def _calculate_raoeo_reserved_cash(strategy_config: Dict) -> float:
    raoeo_conf = strategy_config.get('raoeo', {}).get('targets', {})
    reserved_cash = 0.0

    for target_config in raoeo_conf.values():
        if not target_config.get('enabled', True):
            continue
        seed = float(target_config.get('seed', 0))
        duration = int(target_config.get('duration', 1))
        if duration > 0 and seed > 0:
            reserved_cash += seed / duration

    return reserved_cash


def _rebalancing_reference_asset(
    reb_conf: Dict,
    holdings: Dict,
    prices: Dict[str, float],
) -> Tuple[Any, float]:
    reference_asset = reb_conf.get("assets", [{}])[0].get("ticker")
    reference_holding = holdings.get(reference_asset, {}) if reference_asset else {}
    reference_price = (
        resolve_current_price(reference_asset, reference_holding, prices)
        if reference_asset
        else 0.0
    )
    return reference_asset, reference_price


def _rebalancing_history_context(calc_info: Dict) -> Dict:
    return {
        "seed": calc_info.get("seed"),
        "orderable_usd": calc_info.get("orderable_usd"),
        "total_available": calc_info.get("total_available"),
        "scale_factor": calc_info.get("scale_factor"),
        "asset_status": calc_info.get("asset_status", {}),
    }


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
            _handle_raoeo_history(
                report,
                raoeo_hist,
                execute,
                market_status,
                today_str,
            )
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
            history_data=hist_data,
            today_date=today_str,
        )
        report["orders"] = orders
        report["pending_orders"] = orders
        report["info"].update(calc_info)

        if not orders:
            report["status"] = StrategyStatus.SKIPPED
            if execute and report["info"].get("skipped_buy_budgets"):
                hist_data = _build_strategy_history_data(report, "raoeo")
                _save_strategy_to_history(today_str, "raoeo", hist_data)
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
        _apply_execution_results(report, orders, results)

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
            _handle_va_history(
                report,
                va_hist,
                execute,
                market_status,
                today_str,
            )
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
            _apply_execution_results(report, orders, results)

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

def run_rebalancing_strategy(
    execute: bool = False,
    orderable_cache_key: str = "",
) -> Dict[str, Any]:
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
            _handle_rebalancing_history(report, reb_hist)
            return report

        # Step 5: No history — calculate
        if market_status["is_holiday"]:
            report["status"] = StrategyStatus.HOLIDAY
            return report

        # Load market data (portfolio + prices)
        holdings, prices = get_market_data(force_refresh=True)

        # RAOEO budget reservation
        raoeo_daily_total = _calculate_raoeo_reserved_cash(strategy_config)
        reference_asset, reference_price = _rebalancing_reference_asset(
            reb_conf,
            holdings,
            prices,
        )
        orderable_usd = (
            _get_rebalancing_orderable_usd(
                reference_asset,
                reference_price,
                cache_key=orderable_cache_key,
            )
            if reference_asset and reference_price > 0
            else 0.0
        )

        # Calculate
        orders, calc_info = rebalancing.calculate_orders(
            config=reb_conf,
            portfolio=holdings,
            current_prices=prices,
            orderable_usd=orderable_usd,
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
        _apply_execution_results(report, orders, results)

        # Save history
        save_data = _build_strategy_history_data(report, "rebalancing",
            extra_fields={"context": _rebalancing_history_context(calc_info)})
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
