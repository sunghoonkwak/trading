import json
import logging
import os
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

    price_map = portfolio_data.get('price_map', {})
    merged_portfolio = portfolio_data.get('merged_data', {})

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

    for target_ticker, strategy in targets_config.items():
        # Skip disabled strategies
        if not strategy.get('enabled', True):
            continue

        # Merge with default settings
        merged_strategy = {**default_settings, **strategy}
        exchange = merged_strategy.get('exchange', 'AMS')

        # New Config Params
        daily_budget = merged_strategy.get('daily_budget', 0)
        target_cap = merged_strategy.get('target', 0)
        # Default threshold rate 15% (0.15) if not set
        threshold_rate = merged_strategy.get('threshold_rate', 0.15)

        # Get current price
        current_price = price_map.get(target_ticker, 0.0)
        if current_price <= 0:
            try:
                current_price = fetch_price(target_ticker)
            except Exception:
                pass

        # Get ticker-specific history from list
        ticker_history_entry = None
        ticker_history_date = None

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
        # Use USD value for US stocks (assuming config is in USD)
        current_value = current_value_usd if is_us_stock else current_value_krw

        # Day count calculation
        last_day_count = 0
        using_existing_today_record = False

        if ticker_history_entry:
            last_day_count = ticker_history_entry.get('day_count', 0)
            if ticker_history_date == today_et:
                 using_existing_today_record = True

        if using_existing_today_record:
             day_count = last_day_count
        else:
             day_count = last_day_count + 1

        # Check execution status
        executed_today = False
        executed_orders = []

        if using_existing_today_record:
            results_list = ticker_history_entry.get('results', [])

            # Check if any actual order was executed
            for res in results_list:
                if res.get('executed') and res.get('type') not in ['skip', None]:
                    executed_orders.append({
                        "qty": res.get('qty', 0),
                        "price": res.get('price', 0),
                        "order_type": res.get('order_type', 'LOC'),
                        "type": res.get('type', 'buy'),
                        "time": res.get('time', ''),
                        "message": res.get('message', '')
                    })

            executed_today = bool(executed_orders)

        already_executed = executed_today

        # --- SIMPLIFIED TARGET CALCULATION ---
        target_progress = day_count * daily_budget
        # Cap at target if set
        if target_cap > 0:
            target_value_accumulated = min(target_cap, target_progress)
        else:
            target_value_accumulated = target_progress

        daily_target_amount = target_value_accumulated - current_value

        # Divergence Calculation
        # abs(diff) / target_value
        divergence_rate = 0.0
        # If target_value is 0 (start), we might handle it.
        # But usually target_value >= daily_budget (day 1)
        if target_value_accumulated > 0:
            divergence_rate = abs(daily_target_amount) / target_value_accumulated
        elif daily_target_amount > 0:
            # If target is 0 but we need to buy (start fresh?)
            # This case implies target_value_accumulated is 0.
            # If day_count > 0, target_value should be > 0.
            divergence_rate = 1.0 # Max divergence

        # Determine orders
        orders = []
        if not already_executed and current_price > 0:
            # Check Threshold
            if divergence_rate >= threshold_rate:
                if daily_target_amount > 0:
                    buy_amount = daily_target_amount
                    buy_qty = int(buy_amount / current_price)

                    if buy_qty > 0:
                        order = {
                            "type": "buy_value_averaging",
                            "ticker": target_ticker,
                            "exchange": exchange,
                            "qty": buy_qty,
                            "price": round(current_price * 1.05, 2), # 105% LOC
                            "order_type": "LOC",
                            "desc": f"Value Averaging Day {day_count}",
                            "daily_target": daily_target_amount
                        }
                        orders.append(order)
                        total_orders.append(order)

                elif daily_target_amount < 0:
                    sell_amount = abs(daily_target_amount)
                    sell_qty = int(sell_amount / current_price)

                    if sell_qty > 0:
                        order = {
                            "type": "sell_value_averaging",
                            "ticker": target_ticker,
                            "exchange": exchange,
                            "qty": sell_qty,
                            "price": 0,
                            "order_type": "Market",
                            "desc": f"Value Averaging Sell Day {day_count}",
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
            "target_cap": target_cap,
            "current_value": current_value,
            "daily_target_amount": daily_target_amount,
            "divergence_rate": divergence_rate,
            "threshold_rate": threshold_rate,
            "current_price": current_price,
            "orders": orders,
            "already_executed": already_executed,
            "executed_orders": executed_orders,
            "error": None
        })

    # Determine status
    status = "calculated"
    if is_market_holiday("NYSE"):
        status = "market_holiday"

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
