import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Optional

from kis.kis_api.overseas_stock.order.order import order as order_overseas_stock
from kis.kis_api import kis_auth as ka

# Mapping for exchange codes: short (price fetching) to full (order API)
EXCHANGE_CODE_MAP = {
    "NAS": "NASD",
    "NYS": "NYSE",
    "AMS": "AMEX",
    "NASD": "NASD",
    "NYSE": "NYSE",
    "AMEX": "AMEX",
    "SEHK": "SEHK",
    "SHAA": "SHAA",
    "SZAA": "SZAA",
    "TKSE": "TKSE",
    "HASE": "HASE",
    "VNSE": "VNSE"
}

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
    targets = config.get('targets', {})

    strategy = targets.get(ticker)
    if strategy:
        # Merge default_settings with strategy (strategy takes priority)
        merged = {**default_settings, **strategy}
        return merged
    return {}


def load_history() -> List[Dict[str, Any]]:
    """
    Load value_averaging_history.json.

    Format:
    [
        {
            "date": "2026-02-06",
            "targets": {
                "QLD": {
                    "day_count": 22,
                    "tried_count": 2,
                    "results": [...]
                },
                "TQQQ": { ... }
            }
        },
        ...
    ]
    """
    try:
        if not os.path.exists(HISTORY_FILE):
            return []
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Ensure it's a list
            if isinstance(data, dict):
                # Fallback or empty if old format somehow persists (though we migrated)
                return []
            return data
    except Exception as e:
        logging.error(f"Failed to load value averaging history: {e}")
        return []


def save_history(history_data: List[Dict[str, Any]]) -> bool:
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

    Returns:
        dict: Calculation result with results per ticker and aggregated orders.
    """
    from kis.wrapper import fetch_price
    from data.data_service import get_portfolio_data
    from utils import is_market_holiday

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
    targets_config = config.get('targets', {})
    default_settings = config.get('default_settings', {})

    if not targets_config:
        return {"error": "No targets configured in value_averaging.json"}

    # Load history (list-based)
    hist_data = load_history()
    today_et = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    results = []
    total_orders = []
    config_updated = False

    for target_ticker, strategy in targets_config.items():
        # Skip disabled strategies
        if not strategy.get('enabled', True):
            continue

        # Merge with default settings
        merged_strategy = {**default_settings, **strategy}
        duration = merged_strategy.get('duration', 100)
        exchange = merged_strategy.get('exchange', 'AMS')

        # Get target weight
        target_weight = targets.get(target_ticker, 0.0)

        # Get current price
        current_price = price_map.get(target_ticker, 0.0)
        if current_price <= 0:
            try:
                current_price = fetch_price(target_ticker)
            except Exception:
                pass

        # Get ticker-specific history from list
        # We need to find the latest valid entry for this ticker
        ticker_history_entry = None
        ticker_history_date = None

        # Sort history by date descending just in case, though usually it is.
        # Assuming index 0 is latest for now, but safest to iterate.
        for entry in hist_data:
            if target_ticker in entry.get('targets', {}):
                ticker_history_entry = entry['targets'][target_ticker]
                ticker_history_date = entry['date']
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

        if not ticker_history_entry:  # First run for this ticker
            if target_weight <= 0:
                results.append({
                    "target_ticker": target_ticker,
                    "error": f"Target weight for {target_ticker} is 0 or not found."
                })
                continue

            daily_budget = (total_asset_val * target_weight) / duration
            # Update strategy in config
            if target_ticker in targets_config:
                targets_config[target_ticker]['daily_budget'] = daily_budget
                targets_config[target_ticker]['target_weight_initial'] = target_weight
                config_updated = True

        # Day count calculation
        last_day_count = 0
        using_existing_today_record = False

        if ticker_history_entry:
            last_day_count = ticker_history_entry.get('day_count', 0)

            if ticker_history_date == today_et:
                 using_existing_today_record = True

        # Determine day_count
        if using_existing_today_record:
             # Even if we are re-running (because executed_today is False), we use the SAME day count
             day_count = last_day_count
        else:
             # New day block
             day_count = last_day_count + 1

        # Determine if we should consider this ticker "already finished" for today
        # User wants to re-try if it was only SKIPPED today.
        # So already_executed is True ONLY if we actually BOUGHT specific items today.
        executed_today = False
        executed_orders = [] # Initialize here for scope

        if using_existing_today_record:
            results_list = ticker_history_entry.get('results', [])
            executed_today = any(r.get('executed', False) for r in results_list)

            if executed_today:
                for res in results_list:
                    # Check if any ACTUAL order was placed (type is not skip)
                    if res.get('executed') and res.get('type') not in ['skip', None]:
                        executed_orders.append({
                            "qty": res.get('qty', 0),
                            "price": res.get('price', 0),
                            "order_type": res.get('order_type', 'LOC'),
                            "type": res.get('type', 'buy'),
                            "time": res.get('time', ''),
                            "message": res.get('message', '')
                        })

            # Recalculate 'executed_today' based on whether an ACUTAL order exists
            # intended behavior: if previous attempts were skips, executed_today stays False
            # so we can re-evaluate.
            executed_today = bool(executed_orders)

        already_executed = executed_today

        # Calculate targets and thresholds
        target_value_accumulated = day_count * daily_budget
        current_value = current_value_usd if is_us_stock else current_value_krw

        # 15% Thresholds
        buy_threshold = target_value_accumulated * 0.85
        sell_threshold = target_value_accumulated * 1.15

        daily_target_amount = target_value_accumulated - current_value

        # Determine orders (skip if already executed today)
        orders = []
        if not already_executed and current_price > 0:
            # Case 1: Buy Condition (Current Value < 90% of Target)
            if current_value < buy_threshold:
                # Buy amount = gap to target (fill the hole)
                buy_amount = daily_target_amount
                buy_qty = int(buy_amount / current_price)

                if buy_qty > 0:
                    order = {
                        "type": "buy_value_averaging",
                        "ticker": target_ticker,
                        "exchange": exchange,
                        "qty": buy_qty,
                        "price": round(current_price * 1.00, 2), # 100% LOC
                        "order_type": "LOC",
                        "desc": f"Value Averaging Day {day_count}",
                        "daily_target": daily_target_amount
                    }
                    orders.append(order)
                    total_orders.append(order)

            # Case 2: Sell Condition (Current Value > 110% of Target)
            elif current_value > sell_threshold:
                # Sell amount = Excess amount
                sell_amount = current_value - target_value_accumulated
                sell_qty = int(sell_amount / current_price)

                if sell_qty > 0:
                     order = {
                        "type": "sell_value_averaging",
                        "ticker": target_ticker,
                        "exchange": exchange,
                        "qty": sell_qty,
                        "price": 0, # Market price for sell usually, or we can use 0 for market
                        "order_type": "Market", # User requested Market sell
                        "desc": f"Value Averaging Sell Day {day_count}",
                        "daily_target": -sell_amount # Negative for sell logic indication if needed
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
        config['targets'] = targets_config
        save_config(config)

    # Determine status
    status = "calculated"
    if is_market_holiday("NYSE"):
        status = "market_holiday"
        # Force clear orders on holiday
        for r in results:
            r['orders'] = []
        total_orders = []

    if not results and not total_orders and not error_msg:
         status = "error" if error_msg else "init" # Should not happen if strategies exist

    return {
        "status": status,
        "date": today_et,
        "results": results,
        "total_orders": total_orders,
        "error": None
    }


def execute_single_order(ticker: str, order: dict) -> dict:
    """
    Execute a single order for one ticker.

    Args:
        ticker: Stock ticker symbol
        order: Order dict with qty, price, exchange, order_type, etc.

    Returns:
        dict: Execution result with success, message, etc.
    """
    cano = ka.getTREnv().my_acct
    acnt_prdt_cd = ka.getTREnv().my_prod

    ord_dv = "buy"
    if "sell" in order.get('type', '').lower():
        ord_dv = "sell"

    # For sell, we might need a different order division code or handling
    # order_type mapping: "LOC" -> "34", "Market" -> "00" (usually)
    ord_dvsn = "34" # LOC default
    if order.get('order_type') == "Market":
        ord_dvsn = "00"

    # Map exchange code to ensure compatibility with order API
    ovrs_excg_cd = EXCHANGE_CODE_MAP.get(order['exchange'], order['exchange'])

    res, err_msg = order_overseas_stock(
        cano=cano,
        acnt_prdt_cd=acnt_prdt_cd,
        ovrs_excg_cd=ovrs_excg_cd,
        pdno=ticker,
        ord_qty=str(order['qty']),
        ovrs_ord_unpr=str(order['price']),
        ord_dv=ord_dv,
        ctac_tlno="",
        mgco_aptm_odno="",
        ord_svr_dvsn_cd="0",
        ord_dvsn=ord_dvsn,
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
            "type": order.get('type', 'buy'),
            "qty": order['qty'],
            "price": order['price'],
            "order_type": order.get('order_type', 'LOC'),
            "desc": order.get('desc', ''),
            "daily_target": order.get('daily_target', 0)
        },
        "success": success,
        "message": msg
    }

    return result


def save_ticker_result(ticker: str, day_count: int, result: dict, executed: bool):
    """
    Save a single history entry for one ticker.

    Format:
    {
        "QLD": {
            "YYYY-MM-DD": {
                "day_count": 22,
                "tried_count": N,
                "results": [...]
            }
        }
    }
    """
    hist_data = load_history()
    today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    now_time = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S")

    # Find today's entry
    today_index = -1
    for i, entry in enumerate(hist_data):
        if entry['date'] == today:
            today_index = i
            break

    if today_index == -1:
        # Create new entry for today
        new_entry = {
            "date": today,
            "targets": {}
        }
        hist_data.insert(0, new_entry)
        today_index = 0

    today_entry = hist_data[today_index]

    if ticker not in today_entry["targets"]:
         today_entry["targets"][ticker] = {
            "day_count": day_count,
            "tried_count": 0,
            "results": []
        }

    target_entry = today_entry["targets"][ticker]

    # Flatten result for storage
    order = result.get('order')

    storage_entry = {
        "time": now_time,
        "type": order.get('type', 'skip') if order else 'skip',
        "qty": order.get('qty', 0) if order else 0,
        "price": order.get('price', 0) if order else 0,
        "order_type": order.get('order_type') if order else None,
        "desc": order.get('desc') if order else None,
        "executed": executed,
        "success": result.get('success', False),
        "message": result.get('message', '')
    }

    target_entry["results"].append(storage_entry)
    target_entry["tried_count"] = len(target_entry["results"])

    # Update day_count if this execution actually happened (and it's higher)
    current_day_count = target_entry.get("day_count", 0)
    if day_count > current_day_count:
        target_entry["day_count"] = day_count
    elif current_day_count == 0:
        target_entry["day_count"] = day_count

    save_history(hist_data)
