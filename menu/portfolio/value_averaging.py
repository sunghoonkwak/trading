import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

from kis.kis_api.overseas_stock.order.order import order as order_overseas_stock
from kis.kis_api import kis_auth as ka

# Config / History File Paths (same as kis_auth.py)
CONFIG_ROOT = os.path.join(os.path.expanduser("~"), "KIS_config")
CONFIG_FILE = os.path.join(CONFIG_ROOT, 'value_averaging.json')
HISTORY_FILE = os.path.join(CONFIG_ROOT, 'value_averaging_history.json')


def load_config() -> Dict[str, Any]:
    """Load value_averaging.json config."""
    try:
        if not os.path.exists(CONFIG_FILE):
            return {}
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load value averaging config: {e}")
        return {}


def save_config(config: Dict[str, Any]) -> bool:
    """Save value_averaging.json config."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Failed to save value averaging config: {e}")
        return False


def get_strategy_config(config: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    """Get strategy config for a specific ticker, merging with default_settings."""
    default_settings = config.get('default_settings', {})
    strategies = config.get('strategies', [])

    for strategy in strategies:
        if strategy.get('target') == ticker:
            # Merge default_settings with strategy (strategy takes priority)
            merged = {**default_settings, **strategy}
            return merged
    return {}


def load_history() -> Dict[str, List]:
    """Load value_averaging_history.json. Returns {ticker: [history_entries]}."""
    try:
        if not os.path.exists(HISTORY_FILE):
            return {}
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Handle migration from old format
            if isinstance(data, dict) and 'history' in data and isinstance(data['history'], list):
                # Old format: {"history": [...]} - migrate to new format
                return _migrate_history(data)
            return data
    except Exception as e:
        logging.error(f"Failed to load value averaging history: {e}")
        return {}


def _migrate_history(old_data: Dict[str, Any]) -> Dict[str, List]:
    """Migrate old history format to new ticker-based format."""
    new_history = {}
    for entry in old_data.get('history', []):
        # Extract ticker from first result's order
        results = entry.get('results', [])
        if results:
            ticker = results[0].get('order', {}).get('ticker', 'UNKNOWN')
            if ticker not in new_history:
                new_history[ticker] = []
            # Remove ticker and exchange from order (now stored at top level)
            for r in results:
                if 'order' in r:
                    r['order'].pop('ticker', None)
                    r['order'].pop('exchange', None)
            new_history[ticker].append(entry)
    return new_history


def save_history(history_data: Dict[str, List]) -> bool:
    """Save value_averaging_history.json."""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Failed to save value averaging history: {e}")
        return False


def get_daily_report():
    """
    Calculate the Value Averaging orders for today (supports multiple strategies).

    Args:
        None

    Returns:
        dict: Calculation result with results per ticker and aggregated orders.
    """
    from menu.handle_account_info import fetch_price
    from data.data_service import get_portfolio_data

    # Fetch portfolio data internally
    portfolio_data = get_portfolio_data()
    if portfolio_data.get('error'):
        return {"error": portfolio_data['error']}

    targets = portfolio_data.get('targets', {})
    price_map = portfolio_data.get('price_map', {})
    merged_portfolio = portfolio_data.get('merged_data', {})
    total_value_usd = portfolio_data.get('total_value_usd', 0)
    exchange_rate = portfolio_data.get('exchange_rate', 0)

    config = load_config()
    strategies = config.get('strategies', [])
    default_settings = config.get('default_settings', {})

    if not strategies:
        return {"error": "No strategies configured in value_averaging.json"}

    # Load history (now ticker-based)
    hist_data = load_history()
    today_et = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    results = []
    total_orders = []
    config_updated = False

    for strategy in strategies:
        # Skip disabled strategies
        if not strategy.get('enabled', True):
            continue

        target_ticker = strategy.get('target', '')
        if not target_ticker:
            continue

        # Merge with default settings
        merged_strategy = {**default_settings, **strategy}
        duration = merged_strategy.get('duration', 100)
        exchange = merged_strategy.get('exchange', 'AMEX')

        # Get target weight
        target_weight = targets.get(target_ticker, 0.0)

        # Get current price
        current_price = price_map.get(target_ticker, 0.0)
        if current_price <= 0:
            try:
                current_price = fetch_price(target_ticker)
            except Exception:
                pass

        # Get ticker-specific history
        ticker_history = hist_data.get(target_ticker, [])

        # Check if already executed today with SUCCESS (not failed attempts)
        already_executed = False
        executed_orders = []
        for entry in ticker_history:
            if entry.get('date', '').startswith(today_et) and entry.get('success', False):
                already_executed = True
                # Extract executed order details if available
                results_list = entry.get('results', [])
                if results_list:
                    # In new format, results is a list of dicts
                    for res in results_list:
                        if res.get('order'):
                            executed_orders.append(res['order'])
                break

        # Extract target data from portfolio
        target_data = merged_portfolio.get(target_ticker, {})
        if current_price <= 0:
            current_price = target_data.get('cur_price', 0)

        current_value_usd = target_data.get('current_value_usd', 0)
        current_value_krw = target_data.get('current_value_krw', 0)

        is_us_stock = target_data.get('currency', 'USD') == 'USD'
        total_asset_val = total_value_usd if is_us_stock else (total_value_usd * exchange_rate)

        # Get or initialize daily_budget
        daily_budget = strategy.get('daily_budget', 0)

        if not ticker_history:  # First run for this ticker
            if target_weight <= 0:
                results.append({
                    "target_ticker": target_ticker,
                    "error": f"Target weight for {target_ticker} is 0 or not found."
                })
                continue

            daily_budget = (total_asset_val * target_weight) / duration
            # Update strategy in config
            for s in strategies:
                if s.get('target') == target_ticker:
                    s['daily_budget'] = daily_budget
                    s['target_weight_initial'] = target_weight
                    config_updated = True
                    break

        # Day count calculation: get last successful day_count from history
        # If no history, start at day 1
        last_day_count = 0
        for entry in ticker_history:
            if entry.get('success', False):
                last_day_count = entry.get('day_count', 0)
                break  # History is sorted newest first

        day_count = last_day_count if already_executed else last_day_count + 1

        # Calculate targets
        target_value_accumulated = day_count * daily_budget
        current_value = current_value_usd if is_us_stock else current_value_krw
        daily_target_amount = target_value_accumulated - current_value

        # Determine orders (skip if already executed today)
        orders = []
        if not already_executed and daily_target_amount > 0 and current_price > 0:
            buy_qty = int(daily_target_amount / current_price)
            if buy_qty > 0:
                order = {
                    "type": "buy_value_averaging",
                    "ticker": target_ticker,
                    "exchange": exchange,
                    "qty": buy_qty,
                    "price": round(current_price * 1.05, 2),
                    "order_type": "LOC",
                    "desc": f"Value Averaging Day {day_count}",
                    "daily_target": daily_target_amount
                }
                orders.append(order)
                total_orders.append(order)

        results.append({
            "target_ticker": target_ticker,
            "exchange": exchange,
            "day_count": day_count,
            "daily_budget": daily_budget,
            "target_value_accumulated": target_value_accumulated,
            "current_value": current_value,
            "daily_target_amount": daily_target_amount,
            "current_price": current_price,
            "target_weight": target_weight,
            "orders": orders,
            "already_executed": already_executed,
            "executed_orders": executed_orders,
            "error": None
        })

    # Save updated config if needed
    if config_updated:
        config['strategies'] = strategies
        save_config(config)

    return {
        "status": "calculated",
        "date": today_et,
        "results": results,
        "total_orders": total_orders,
        "error": None
    }


def execute_orders(order_report):
    """
    Execute the calculated orders for all strategies.
    Records history for all strategies (including those with no orders).
    """
    if not order_report:
        return []

    results = order_report.get('results', [])
    total_orders = order_report.get('total_orders', [])

    if not results:
        return []

    today_et = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    hist_data = load_history()

    exec_results = []

    # KIS Auth Credentials
    cano = ka.getTREnv().my_acct
    acnt_prdt_cd = ka.getTREnv().my_prod

    # Build order map and day_count map for quick lookup
    order_map = {o['ticker']: o for o in total_orders}
    day_count_map = {r['target_ticker']: r.get('day_count', 0) for r in results if r.get('target_ticker')}

    for r in results:
        if r.get('error'):
            continue

        ticker = r.get('target_ticker')
        if not ticker:
            continue

        # Skip if already processed today with SUCCESS (failed attempts should retry)
        ticker_history = hist_data.get(ticker, [])
        already_success_today = any(
            entry.get('date', '').startswith(today_et) and entry.get('success', False)
            for entry in ticker_history
        )

        if already_success_today:
            logging.info(f"Value Averaging for {ticker} already succeeded today ({today_et} ET). Skipping.")
            exec_results.append({
                "ticker": ticker,
                "skipped": True,
                "message": f"Already succeeded today ({today_et} ET)"
            })
            continue

        # Check if there's an order for this ticker
        order = order_map.get(ticker)

        if order and order.get('order_type') == 'LOC':
            # Execute the order
            res, err_msg = order_overseas_stock(
                cano=cano,
                acnt_prdt_cd=acnt_prdt_cd,
                ovrs_excg_cd=order['exchange'],
                pdno=ticker,
                ord_qty=str(order['qty']),
                ovrs_ord_unpr=str(order['price']),
                ord_dv="buy",
                ctac_tlno="",
                mgco_aptm_odno="",
                ord_svr_dvsn_cd="0",
                ord_dvsn="34",  # LOC
                env_dv="demo" if ka.isPaperTrading() else "real"
            )

            success = False
            msg = "Failed"
            if res is not None and not res.empty:
                success = True
                msg = "Order Placed"
            elif err_msg:
                msg = err_msg

            result = {
                "ticker": ticker,
                "order": {
                    "type": order['type'],
                    "qty": order['qty'],
                    "price": order['price'],
                    "order_type": order['order_type'],
                    "desc": order['desc'],
                    "daily_target": order['daily_target']
                },
                "success": success,
                "message": msg
            }
        else:
            # No order (qty=0 or insufficient budget) - still record the day
            result = {
                "ticker": ticker,
                "order": None,
                "success": True,  # Day recorded successfully
                "message": "No order needed (insufficient qty)"
            }

        exec_results.append(result)

        # Save to ticker-specific history
        if ticker not in hist_data:
            hist_data[ticker] = []

        history_entry = {
            "date": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S"),
            "day_count": day_count_map.get(ticker, 0),
            "results": [result],
            "success": result.get('success', False)
        }
        hist_data[ticker].insert(0, history_entry)

    # Save all history updates
    if exec_results:
        save_history(hist_data)

    return exec_results
