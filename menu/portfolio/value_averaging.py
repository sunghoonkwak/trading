import logging
import math
from datetime import datetime, timezone

from .value_averaging_config import load_config, save_config, load_history, save_history
from menu.handle_account_info import fetch_account_data
from trading_config import get_kis_exchange_code
import display
from kis_api.overseas_stock.order.order import order as order_overseas_stock
import kis_api.kis_auth as ka



def calculate_order(merged_portfolio, total_value_usd, target_weight=0.0, current_price=0.0):
    """
    Calculate the Value Averaging order for today.

    Args:
        merged_portfolio (dict): Portfolio data with current holdings and prices.
        total_value_usd (float): Total asset value in USD.
        target_weight (float): Target weight for the target ticker (0.0 - 1.0).
        current_price (float): Current market price of the target ticker (optional override).
    """
    config = load_config()
    target_ticker = config.get('target', '')
    if not target_ticker:
        return {"error": "No target ticker configured in value_averaging.json"}

    duration = config.get('duration', 100)
    exchange = config.get('exchange', 'AMEX')

    # 1. Load History & State
    hist_data = load_history()
    history = hist_data.get('history', [])

    # Check if we already have a success record for today
    today_str = datetime.now().strftime("%Y-%m-%d")
    already_done = False
    if history and history[0].get('date') == today_str and history[0].get('success', False):
         already_done = True
         # If already done, we might just return the record or specific status
         # But the user might want to see the report anyway. For now, proceed calculation for reporting.

    # 2. Extract Target Data from Injected Portfolio
    target_data = merged_portfolio.get(target_ticker, {})
    current_qty = target_data.get('qty', 0)

    # Use injected price if stronger/available, else fall back to portfolio data
    if current_price <= 0:
        current_price = target_data.get('cur_price', 0)

    current_value_usd = target_data.get('current_value_usd', 0)
    current_value_krw = target_data.get('current_value_krw', 0)

    # Get Total Asset Value in KRW
    # Assuming standard approximate rate if not provided or contained in metadata
    # Use 1435 for now or implicit logic
    is_us_stock = target_data.get('currency', 'USD') == 'USD'
    total_asset_val = total_value_usd if is_us_stock else (total_value_usd * 1435)

    # 3. Initialize if needed (First Run)
    daily_budget = config.get('daily_budget', 0)

    if not history: # Initial State
        if target_weight <= 0:
             return {"error": f"Target weight for {target_ticker} is 0 or not found."}

        # Formula: Daily Budget = (Total Assets * Target Weight) / Duration
        daily_budget = (total_asset_val * target_weight) / duration

        config['daily_budget'] = daily_budget
        config['target_weight_initial'] = target_weight
        save_config(config)

    day_count = len([h for h in history if h.get('success')]) + 1

    # 4. Calculate Targets
    target_value_accumulated = day_count * daily_budget
    current_value = current_value_usd if is_us_stock else current_value_krw

    daily_target_amount = target_value_accumulated - current_value

    # 5. Determine Orders
    orders = []

    if daily_target_amount > 0 and current_price > 0:
        buy_qty = int(daily_target_amount / current_price)

        if buy_qty > 0:
             # Strategy: LOC at +10% to ensure fill
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
