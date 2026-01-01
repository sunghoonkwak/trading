import json
import logging
import os
from datetime import datetime
from typing import Dict, Any

from kis_api.overseas_stock.order.order import order as order_overseas_stock
import kis_api.kis_auth as ka

# Config / History File Paths
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'value_averaging.json')
HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'value_averaging_history.json')


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


def load_history() -> Dict[str, Any]:
    """Load value_averaging_history.json."""
    try:
        if not os.path.exists(HISTORY_FILE):
            return {"history": []}
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load value averaging history: {e}")
        return {"history": []}


def save_history(history_data: Dict[str, Any]) -> bool:
    """Save value_averaging_history.json."""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Failed to save value averaging history: {e}")
        return False



def calculate_order(targets: dict, price_map: dict, merged_portfolio: dict, total_value_usd: float):
    """
    Calculate the Value Averaging order for today.

    Args:
        targets (dict): Target weights per ticker {ticker: weight}.
        price_map (dict): Current prices per ticker {ticker: price}.
        merged_portfolio (dict): Portfolio data with current holdings.
        total_value_usd (float): Total asset value in USD.

    Returns:
        dict: Calculation result with orders, status, and metrics.
    """
    from menu.handle_account_info import fetch_price

    # 1. Load Config
    config = load_config()
    target_ticker = config.get('target', '')
    if not target_ticker:
        return {"error": "No target ticker configured in value_averaging.json"}

    duration = config.get('duration', 100)
    exchange = config.get('exchange', 'AMEX')

    # 2. Get Target Weight from targets dict
    target_weight = targets.get(target_ticker, 0.0)

    # 3. Get Current Price from price_map, fallback to fetch_price
    current_price = price_map.get(target_ticker, 0.0)
    if current_price <= 0:
        try:
            current_price = fetch_price(target_ticker)
        except Exception:
            pass  # Will be handled below if still 0

    # 4. Load History & State
    hist_data = load_history()
    history = hist_data.get('history', [])

    today_str = datetime.now().strftime("%Y-%m-%d")

    # 5. Extract Target Data from Portfolio
    target_data = merged_portfolio.get(target_ticker, {})

    # Use portfolio price as secondary fallback
    if current_price <= 0:
        current_price = target_data.get('cur_price', 0)

    current_value_usd = target_data.get('current_value_usd', 0)
    current_value_krw = target_data.get('current_value_krw', 0)

    is_us_stock = target_data.get('currency', 'USD') == 'USD'
    total_asset_val = total_value_usd if is_us_stock else (total_value_usd * 1435)

    # 6. Initialize Daily Budget if First Run
    daily_budget = config.get('daily_budget', 0)

    if not history:  # Initial State
        if target_weight <= 0:
            return {"error": f"Target weight for {target_ticker} is 0 or not found."}

        daily_budget = (total_asset_val * target_weight) / duration
        config['daily_budget'] = daily_budget
        config['target_weight_initial'] = target_weight
        save_config(config)

    day_count = len([h for h in history if h.get('success')]) + 1

    # 7. Calculate Targets
    target_value_accumulated = day_count * daily_budget
    current_value = current_value_usd if is_us_stock else current_value_krw

    daily_target_amount = target_value_accumulated - current_value

    # 8. Determine Orders
    orders = []

    if daily_target_amount > 0 and current_price > 0:
        buy_qty = int(daily_target_amount / current_price)

        if buy_qty > 0:
            orders.append({
                "type": "buy_value_averaging",
                "ticker": target_ticker,
                "exchange": exchange,
                "qty": buy_qty,
                "price": round(current_price * 1.1, 2),
                "order_type": "LOC",
                "desc": f"Value Averaging Day {day_count}",
                "daily_target": daily_target_amount
            })

    return {
        "status": "calculated",
        "date": today_str,
        "target_ticker": target_ticker,
        "day_count": day_count,
        "daily_budget": daily_budget,
        "target_value_accumulated": target_value_accumulated,
        "current_value": current_value,
        "daily_target_amount": daily_target_amount,
        "current_price": current_price,
        "target_weight": target_weight,
        "orders": orders,
        "error": None
    }

def execute_orders(order_report):
    """
    Execute the calculated orders.
    """
    if not order_report or not order_report.get('orders'):
        return []

    results = []

    # KIS Auth Credentials
    cano = ka.getTREnv().my_acct
    acnt_prdt_cd = ka.getTREnv().my_prod

    for order in order_report['orders']:
        # Only LOC supported for now as per request
        if order['order_type'] != 'LOC':
            continue

        # order.py signature:
        # order(cano, acnt_prdt_cd, ovrs_excg_cd, pdno, ord_qty, ovrs_ord_unpr, ord_dv, ...)

        # Ensure qty and price are strings for API if needed, order.py wrapper usually expects strings or converts?
        # Looking at order.py: ord_qty: str, ovrs_ord_unpr: str. So we must convert.

        # ord_dvsn="34" for LOC

        res, err_msg = order_overseas_stock(
            cano=cano,
            acnt_prdt_cd=acnt_prdt_cd,
            ovrs_excg_cd=order['exchange'],
            pdno=order['ticker'],
            ord_qty=str(order['qty']),
            ovrs_ord_unpr=str(order['price']), # For LOC, this is the limit price
            ord_dv="buy",
            ctac_tlno="",
            mgco_aptm_odno="",
            ord_svr_dvsn_cd="0",
            ord_dvsn="34", # LOC
            env_dv="demo" if ka.isPaperTrading() else "real"
        )

        success = False
        msg = "Failed"
        if res is not None and not res.empty:
             success = True
             msg = "Order Placed" # Can get more details from res if needed
        elif err_msg:
             msg = err_msg

        results.append({
            "order": order,
            "success": success,
            "message": msg
        })

    # Trigger Save History will be handled by the caller (Telegram Bot logic usually)
    # But for now, we just return results.

    return results
