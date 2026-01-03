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
import msvcrt
from datetime import datetime
from typing import Optional
import pytz

from kis.kis_api import kis_auth as ka
from display import (
    clear_result_area, show_in_result_area, input_at,
    render_ui
)
from data.data_service import get_portfolio_data
from kis.kis_api.overseas_stock.order.order import order as order_overseas
import trading_state
import trading_config

# Module directory for config files
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(MODULE_DIR, "raoeo.json")
HISTORY_FILE = os.path.join(MODULE_DIR, "raoeo_history.json")

# LOC order type code for US stocks
LOC_ORDER_TYPE = "34"
LIMIT_ORDER_TYPE = "00"


def load_config() -> dict:
    """
    Load configuration from raoeo.json.
    """
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        config = data.get('config', {})

        # Validate required fields
        required = ['seed', 'target', 'duration']
        for field in required:
            if field not in config:
                raise ValueError(f"Missing required config field: {field}")

        # Set defaults
        config.setdefault('exchange', 'NASD')
        config.setdefault('sell_profit', 0.10)

        return config
    except FileNotFoundError:
        display.add_alert(f"Config file not found: {CONFIG_FILE}", "ERROR")
        return {}
    except json.JSONDecodeError as e:
        display.add_alert(f"Invalid JSON in config: {e}", "ERROR")
        return {}


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


def calculate_order() -> dict:
    """
    Calculate buy/sell orders for today based on the RAOEO strategy.

    Strategy:
        - Initial state (no holdings): LOC buy at current_price * 110%
        - Holding state:
            - Sell: Limit order at avg_price * (1 + sell_profit)
            - LOC buy 1: 50% budget at avg_price * (1 + (sell_profit - 1%)) (guaranteed execution)
            - LOC buy 2: 50% budget at avg_price * 100% (lower avg cost)

    Returns:
        dict: Order calculation result with date, config, holdings, orders
    """
    tz_us = pytz.timezone('US/Eastern')
    result = {
        "date": datetime.now(tz_us).strftime("%Y-%m-%d"),
        "state": None,
        "config": {},
        "holdings": {},
        "daily_budget": 0.0,
        "orders": [],
        "error": None
    }

    # 1. Load config
    config = load_config()
    if not config:
        result["error"] = "Failed to load config"
        return result

    result["config"] = config
    seed = float(config['seed'])
    target = config['target']

    # Try to get correct exchange from global config, fallback to local raoeo.json info
    exchange = config.get('exchange', 'NASD')
    stock_info = trading_config.get_stock_info(target)
    if stock_info:
        mkt = stock_info.get('market', '').upper()
        excg_map = {"NASDAQ": "NASD", "NYSE": "NYSE", "AMEX": "AMEX", "NASDAQ/AMEX": "AMEX"}
        if mkt in excg_map:
            exchange = excg_map[mkt]
            # Update config in result to show actual exchange used
            result["config"]["exchange"] = exchange

    duration = int(config['duration'])
    sell_profit = float(config.get('sell_profit', 0.10))

    # 2. Calculate daily budget
    daily_budget = seed / duration
    result["daily_budget"] = round(daily_budget, 2)

    # 3. Fetch current holdings from portfolio data
    portfolio = get_portfolio_data()
    if portfolio.get('error'):
        result["error"] = portfolio['error']
        return result

    # Find target stock in merged holdings
    merged = portfolio.get('merged_data', {})
    target_holding = None
    for ticker, info in merged.items():
        if ticker.upper() == target.upper():
            qty = info.get('qty', 0)
            total_investment = info.get('total_investment', 0)
            avg_price = total_investment / qty if qty > 0 else 0
            target_holding = {
                'symbol': ticker,
                'qty': qty,
                'avg_price': avg_price,
                'cur_price': info.get('cur_price', 0)
            }
            break

    # 4. Get current price: KIS API -> WebSocket
    from menu.handle_account_info import fetch_price
    cur_price = fetch_price(target)
    if cur_price <= 0:
        cur_price = get_current_price(target, exchange)

    # 5. Calculate orders based on state
    if target_holding is None or target_holding.get('qty', 0) == 0:
        # Initial state - no holdings
        result["state"] = "initial"
        result["holdings"] = {"qty": 0, "avg_price": 0, "cur_price": cur_price}

        if cur_price <= 0:
            result["error"] = f"Waiting for {target} price data from WebSocket. Please try again shortly."
            return result

        # LOC buy at 110% of current price (guaranteed execution at close)
        buy_price = round(cur_price * 1.10, 2)
        buy_qty = int(daily_budget / buy_price)

        if buy_qty > 0:
            result["orders"].append({
                "type": "buy_initial",
                "price": buy_price,
                "qty": buy_qty,
                "order_type": "LOC",
                "type_code": LOC_ORDER_TYPE,
                "desc": "Initial buy at 110% of current price"
            })
    else:
        # Holding state
        result["state"] = "holding"
        qty = int(target_holding.get('qty', 0))
        avg_price = float(target_holding.get('avg_price', 0))

        result["holdings"] = {
            "qty": qty,
            "avg_price": round(avg_price, 2),
            "cur_price": cur_price
        }

        if avg_price <= 0:
            result["error"] = f"Invalid average price for {target}"
            return result

        # Sell order: all holdings at avg + profit
        sell_price = round(avg_price * (1 + sell_profit), 2)

        result["orders"].append({
            "type": "sell_all",
            "price": sell_price,
            "qty": qty,
            "order_type": "LIMIT",
            "type_code": LIMIT_ORDER_TYPE,
            "desc": f"Sell all at {int(sell_profit*100)}% profit"
        })

        # Calculate total quantity for today's budget based on avg_price
        # Logic: Total Qty = Budget / AvgPrice
        # Buy 1: (Total / 2) + Remainder
        # Buy 2: (Total / 2)
        total_buy_qty = int(daily_budget / avg_price)
        buy_qty_1 = (total_buy_qty // 2) + (total_buy_qty % 2)
        buy_qty_2 = total_buy_qty // 2

        # Buy order 1: 1% lower than sell target (guaranteed execution, avoid self-match)
        buy_ratio_1 = 1 + sell_profit - 0.01
        buy_price_1 = round(avg_price * buy_ratio_1, 2)

        if buy_qty_1 > 0:
            result["orders"].append({
                "type": "buy_guaranteed",
                "price": buy_price_1,
                "qty": buy_qty_1,
                "order_type": "LOC",
                "type_code": LOC_ORDER_TYPE,
                "desc": f"Buy at {int(buy_ratio_1*100)}% of avg (guaranteed)"
            })

        # Buy order 2: at 100% (lower avg)
        buy_price_2 = round(avg_price * 1.00, 2)

        if buy_qty_2 > 0:
            result["orders"].append({
                "type": "buy_lower",
                "price": buy_price_2,
                "qty": buy_qty_2,
                "order_type": "LOC",
                "type_code": LOC_ORDER_TYPE,
                "desc": "Buy at 100% of avg (lower cost)"
            })


    return result


def execute_orders(orders: list, config: dict) -> list:
    """
    Execute the calculated orders via KIS API.

    Args:
        orders: List of order dicts from calculate_order()
        config: Configuration dict with target, exchange

    Returns:
        list: Execution results for each order
    """
    results = []
    cano = ka.getTREnv().my_acct
    prod = ka.getTREnv().my_prod
    target = config['target']
    exchange = config.get('exchange', 'NASD')

    for order in orders:
        try:
            df, err = order_overseas(
                cano=cano,
                acnt_prdt_cd=prod,
                ovrs_excg_cd=exchange,
                pdno=target,
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
            results.append({
                "order": order,
                "success": success,
                "error": err if not success else None,
                "response": df.to_dict('records') if success else None
            })
        except Exception as e:
            results.append({
                "order": order,
                "success": False,
                "error": str(e)
            })

    return results


def save_history(order_data: dict, exec_results: list = None) -> bool:
    """
    Save order calculation and execution results to history file.

    Args:
        order_data: Result from calculate_order()
        exec_results: Optional list of execution results from execute_orders()
    """
    try:
        # Ensure date is set
        if not order_data.get('date'):
            tz_us = pytz.timezone('US/Eastern')
            order_data['date'] = datetime.now(tz_us).strftime("%Y-%m-%d")

        # Merge execution info into order_data
        if exec_results:
            # Match each order with its result
            for order in order_data.get('orders', []):
                result = next((r for r in exec_results if r['order'] == order), None)
                if result:
                    order['success'] = result['success']
                    order['error'] = result.get('error')

        # Load existing history
        history = {"history": []}
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        loaded = json.loads(content)
                        # Filter out entries without date
                        history["history"] = [e for e in loaded.get('history', []) if e.get('date')]
            except (json.JSONDecodeError, IOError):
                pass

        # Check if today's entry already exists
        today_str = order_data.get('date')
        existing_entry = None
        for entry in history.get('history', []):
            if entry.get('date') == today_str:
                existing_entry = entry
                break

        if existing_entry:
            # Update existing entry with new order results
            for new_order in order_data.get('orders', []):
                # match by the descriptive 'type' (which acts as ID)
                old_matching = None
                for old_order in existing_entry.get('orders', []):
                    if old_order.get('type') == new_order.get('type'):
                        old_matching = old_order
                        break

                if old_matching:
                    if new_order.get('success'):
                        old_matching['success'] = True
                        old_matching['error'] = None
                    elif not old_matching.get('success'):
                        old_matching['error'] = new_order.get('error')
        else:
            # Insert new entry at the beginning
            history["history"].insert(0, order_data)

        # Save
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f_out:
            json.dump(history, f_out, indent=4, ensure_ascii=False)

        return True
    except Exception as e:
        from display import add_alert
        add_alert(f"Failed to save history: {e}", "ERROR")
        return False


def check_today_history() -> Optional[dict]:
    """
    Check if RAOEO strategy was executed today.

    Returns:
        Optional[dict]: Today's execution record if exists, None otherwise
    """
    tz_us = pytz.timezone('US/Eastern')
    today_str = datetime.now(tz_us).strftime("%Y-%m-%d")

    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    history_data = json.loads(content)
                    for entry in history_data.get('history', []):
                        if entry.get('date') == today_str:
                            return entry
    except Exception as e:
        display.add_alert(f"Error checking history: {e}", "ERROR")

    return None


def build_raoeo_report() -> dict:
    """
    Build RAOEO status report for both terminal and Telegram.

    Returns:
        dict: Report containing:
            - executed_today: Today's execution record if exists
            - current_result: Calculated order result if not executed
            - cur_price: Current price fetched from KIS API/WebSocket/holdings
            - config: Config from current_result or history
            - holdings: Holdings from current_result or history
            - success_orders: List of successfully executed orders
            - failed_orders: List of failed orders
            - pending_orders: List of pending orders to be placed
            - error: Error message if any
    """
    report = {
        "executed_today": None,
        "current_result": None,
        "cur_price": 0.0,
        "config": None,
        "holdings": None,
        "success_orders": [],
        "failed_orders": [],
        "pending_orders": [],
        "error": None
    }
    tz_us = pytz.timezone('US/Eastern')
    today_str = datetime.now(tz_us).strftime("%Y-%m-%d")

    # 1. Check history first - if some failed, we prioritize retrying those EXACT orders
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    hist = json.loads(content)
                    # Filter out entries without date and get the first one
                    entries = [e for e in hist.get('history', []) if e.get('date')]
                    today_entry = entries[0] if entries and entries[0].get('date') == today_str else None
                    if today_entry:
                        report["config"] = today_entry.get('config')
                        report["holdings"] = today_entry.get('holdings')

                        # Categorize orders from history
                        for o in today_entry.get('orders', []):
                            if o.get('success'):
                                report["success_orders"].append(o)
                            else:
                                report["failed_orders"].append(o)

                        if not report["failed_orders"]:
                            # Everything succeeded
                            report["executed_today"] = today_entry
                        else:
                            # Some failed! Populate current_result with THESE failed orders for retry
                            report["current_result"] = {
                                "date": today_str,
                                "config": today_entry['config'],
                                "holdings": today_entry['holdings'],
                                "orders": report["failed_orders"],
                                "state": today_entry.get('state', 'unknown'),
                                "is_retry": True
                            }
        except Exception as e:
            display.add_alert(f"Error reading history for report: {e}", "ERROR")

    # 2. No history for today yet - calculate fresh orders
    if not report["executed_today"] and not report["current_result"]:
        current_result = calculate_order()
        if current_result.get('error'):
            report["error"] = current_result['error']
        report["current_result"] = current_result
        report["config"] = current_result.get('config')
        report["holdings"] = current_result.get('holdings')

    # 3. Calculate pending orders from current_result
    # Note: failed_orders should be retried, so they go into pending_orders
    # Only exclude orders that have already succeeded
    if report.get("current_result"):
        success_types = {o.get('type') for o in report["success_orders"]}
        for o in report["current_result"].get('orders', []):
            if o.get('type') not in success_types:
                report["pending_orders"].append(o)

    # 4. Fetch current price: KIS API -> WebSocket -> holdings
    config = report.get("config")
    holdings = report.get("holdings") or {}
    if config:
        from menu.handle_account_info import fetch_price
        cur_price = fetch_price(config['target'])  # auto-maps exchange code
        if cur_price <= 0:
            cur_price = get_current_price(config['target'], config.get('exchange', 'NASD'))
        if cur_price <= 0:
            cur_price = holdings.get('cur_price', 0)
        report["cur_price"] = cur_price

    return report


def format_display_lines(report: dict) -> list:
    """Format report for terminal display with color-coded status."""
    from display import COLOR_GREEN, COLOR_RED, COLOR_RESET, COLOR_YELLOW
    tz_us = pytz.timezone('US/Eastern')
    today_str = datetime.now(tz_us).strftime("%Y-%m-%d")
    display_lines = []

    # Get pre-calculated values from report
    config = report.get("config")
    holdings = report.get("holdings") or {}
    cur_price = report.get("cur_price", 0)
    success_orders = report.get("success_orders", [])
    failed_orders = report.get("failed_orders", [])
    pending_orders = report.get("pending_orders", [])

    if not config:
        if report.get("error"): return [f" Error: {report['error']}"]
        return [" No RAOEO data."]

    display_lines.append(f" [RAOEO Status - {today_str}]")
    display_lines.append(f" Target: {config['target']} @ {config['exchange']} | Cur: ${cur_price:.2f}")
    display_lines.append(f" Holdings: {holdings.get('qty', 0)} shares @ ${holdings.get('avg_price', 0):.2f}")
    display_lines.append("")

    # Orders Section (Success/Failed with retry indicator)
    if success_orders or failed_orders or pending_orders:
        display_lines.append(" Orders:")
        for o in success_orders:
            display_lines.append(f"   {COLOR_GREEN}• {o['type'].upper()} {o['qty']} @ ${o['price']:.2f} ({o['order_type']}) - Success{COLOR_RESET}")
        for o in failed_orders:
            err = f" ({o['error'][:25]})" if o.get('error') else ""
            display_lines.append(f"   {COLOR_YELLOW}• {o['type'].upper()} {o['qty']} @ ${o['price']:.2f} ({o['order_type']}) - Failed → Retry{err}{COLOR_RESET}")
        # Show new pending orders (not from failed retry)
        failed_types = {o.get('type') for o in failed_orders}
        for o in pending_orders:
            if o.get('type') not in failed_types:
                display_lines.append(f"   {COLOR_YELLOW}• {o['type'].upper()} {o['qty']} @ ${o['price']:.2f} ({o['order_type']}) - Pending{COLOR_RESET}")
        display_lines.append("")

    if not pending_orders and not failed_orders:
        display_lines.append(f" {COLOR_GREEN}✨ All orders completed for today.{COLOR_RESET}")

    # Menu - always show both options
    display_lines.append(" 1. Order  2. History")
    display_lines.append("-" * 50)
    return display_lines


def prompt_order_execution(report: dict, display_lines: list) -> bool:
    """
    Handle menu option 1: Prompt user to confirm order execution.

    Args:
        report: Result from build_raoeo_report()
        display_lines: Current display lines for context

    Returns:
        bool: True if orders were executed, False otherwise
    """
    pending_orders = report.get("pending_orders", [])
    if not pending_orders:
        from display import add_alert
        add_alert("No pending orders to execute.", "INFO")
        return False

    input_y = min(len(display_lines) + 1, 14)
    action = input_at(input_y, 2, " Place order? (y/N): ").strip().lower()

    if action == 'y':
        # Create a result dict for run_order_execution
        exec_data = {
            "config": report.get("config"),
            "holdings": report.get("holdings"),
            "orders": pending_orders
        }
        return run_order_execution(exec_data, display_lines)

    return False


def run_order_execution(result: dict, display_lines: list) -> bool:
    """
    Execute orders and save to history.

    Args:
        result: Order calculation result from calculate_order()
        display_lines: Current display lines for context

    Returns:
        bool: True if execution successful
    """
    show_in_result_area(display_lines + [" Executing orders... Please wait."])

    exec_results = execute_orders(result['orders'], result['config'])

    # Display results
    from display import COLOR_GREEN, COLOR_RED, COLOR_RESET
    res_lines = [" [Execution Results]"]
    success_count = 0
    for i, res in enumerate(exec_results, 1):
        status = f"{COLOR_GREEN}OK{COLOR_RESET}" if res['success'] else f"{COLOR_RED}FAIL{COLOR_RESET}"
        if res['success']: success_count += 1
        o = res['order']
        err = f" ({res['error'][:30]})" if not res['success'] and res.get('error') else ""
        res_lines.append(f" {i}. {o['type'].upper()} {o['qty']}@{o['price']} - {status}{err}")

    save_history(result, exec_results)
    res_lines.append("")
    res_lines.append(f" Result: {success_count}/{len(exec_results)} succeeded.")
    res_lines.append(" Press any key...")
    show_in_result_area(res_lines)
    msvcrt.getch()

    return True


def show_history_viewer():
    """
    Display history with pagination (menu option 2).
    """
    try:
        if not os.path.exists(HISTORY_FILE):
            show_in_result_area([" No history found.", "", " Press any key..."])
            msvcrt.getch()
            return

        with open(HISTORY_FILE, 'r', encoding='utf-8') as f_hist:
            content = f_hist.read().strip()
            if not content:
                show_in_result_area([" History is empty.", "", " Press any key..."])
                msvcrt.getch()
                return
            history_data = json.loads(content)

        all_entries = history_data.get('history', [])
        if not all_entries:
            show_in_result_area([" No entries in history.", "", " Press any key..."])
            msvcrt.getch()
            return

        entries = all_entries
        offset = 0
        page_size = 5

        while True:
            clear_result_area()
            total = len(entries)
            current_page = (offset // page_size) + 1
            total_pages = (total + page_size - 1) // page_size

            display_lines = [
                f" [RAOEO History] Page {current_page}/{total_pages} ({total} entries)",
                " " + "-" * 100,
                " Date       | State   | AvgPrc | CurPrc | Orders",
                " " + "-" * 100
            ]

            page_entries = entries[offset:offset+page_size]
            for entry in page_entries:
                date = entry.get('date', 'N/A')
                state = f"{entry.get('state', 'N/A'):<7}"
                holdings = entry.get('holdings', {})
                avg = f"{float(holdings.get('avg_price', 0)):>6.2f}"
                cur = f"{float(holdings.get('cur_price', 0)):>6.2f}"

                ord_strs = []
                for o in entry.get('orders', []):
                    if o.get('success') is False:
                        continue
                    o_type = o.get('type', 'buy').lower()
                    o_qty = o.get('qty', 0)
                    o_prc = float(o.get('price', 0))
                    ord_strs.append(f"{o_type}:{o_qty}(${o_prc:.2f})")

                orders_txt = ", ".join(ord_strs)
                display_lines.append(f" {date} | {state} | {avg} | {cur} | {orders_txt}")

            for _ in range(page_size - len(page_entries)):
                display_lines.append("")

            display_lines.append(" " + "-" * 100)
            display_lines.append(" (f) Next 5 items | (g) Back to Start | (q) Back to Menu")

            show_in_result_area(display_lines)
            sys.stdout.write("\033[13;2H")
            sys.stdout.flush()

            try:
                ch = msvcrt.getch().decode('utf-8').lower()
            except:
                ch = ''

            if ch == 'q':
                break
            elif ch == 'f':
                offset += page_size
                if offset >= total:
                    offset = 0
            elif ch == 'g':
                offset = 0

    except Exception as e:
        show_in_result_area([f" Error reading history: {e}", "", " Press any key..."])
        msvcrt.getch()


def raoeo_menu():
    """RAOEO strategy menu interface using modular functions."""
    os.system('cls' if os.name == 'nt' else 'clear')

    while True:
        # Build report using modular function
        report = build_raoeo_report()

        # Format display using modular function
        display_lines = format_display_lines(report)

        # Display content first, then render Orders/Alerts below
        show_in_result_area(display_lines)
        render_ui(full_refresh=False)

        input_y = min(len(display_lines) + 1, 13)
        choice = input_at(input_y, 2, " Select(q: exit): ").strip().lower()

        if choice == 'q':
            break

        elif choice == '1':
            prompt_order_execution(report, display_lines)

        elif choice == '2':
            show_history_viewer()

    render_ui(full_refresh=True)

