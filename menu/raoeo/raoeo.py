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

import kis_api.kis_auth as ka
from display import (
    clear_result_area, show_in_result_area, input_at,
    render_ui, PrintLevel, print_log
)
from menu.handle_account_info import fetch_overseas_balance
from kis_api.overseas_stock.order.order import order as order_overseas
import trading_state
import trading_config

# Module directory for config files
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(MODULE_DIR, "raoeo.json")
HISTORY_FILE = os.path.join(MODULE_DIR, "raoeo_history.json")

# LOC order type code for US stocks
LOC_ORDER_TYPE = "34"


def load_config() -> dict:
    """
    Load configuration from raoeo.json.

    Returns:
        dict: Configuration with keys: seed, target, exchange, duration, sell_profit
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
        print_log(PrintLevel.ERROR, f"Config file not found: {CONFIG_FILE}")
        return {}
    except json.JSONDecodeError as e:
        print_log(PrintLevel.ERROR, f"Invalid JSON in config: {e}")
        return {}


def get_current_price(symbol: str, exchange: str = "NASD") -> float:
    """
    Fetch current price for an overseas stock from WebSocket subscription.
    Returns 0.0 if data not yet received (caller should retry).

    Args:
        symbol: Stock ticker (e.g., "SOXL")
        exchange: Exchange code (e.g., "NASD")

    Returns:
        float: Current stock price, or 0.0 if not available
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
            - LOC buy 1: 50% budget at avg_price * 115% (guaranteed execution)
            - LOC buy 2: 50% budget at avg_price * 100% (lower avg cost)
            - LOC sell:  all holdings at avg_price * (1 + sell_profit)

    Returns:
        dict: Order calculation result with date, config, holdings, orders
    """
    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
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

    # 3. Fetch current holdings
    us_balance = fetch_overseas_balance()
    if us_balance.get('error'):
        result["error"] = us_balance['error']
        return result

    # Find target stock in holdings
    target_holding = None
    for stock in us_balance.get('stocks', []):
        if stock.get('symbol', '').upper() == target.upper():
            target_holding = stock
            break

    # 4. Get current price
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
                "type": "buy",
                "price": buy_price,
                "qty": buy_qty,
                "order_type": "LOC",
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

        # Buy order 1: 50% at 115% (guaranteed execution)
        buy_price_1 = round(avg_price * 1.15, 2)
        buy_budget_1 = daily_budget * 0.5
        buy_qty_1 = int(buy_budget_1 / buy_price_1)

        if buy_qty_1 > 0:
            result["orders"].append({
                "type": "buy",
                "price": buy_price_1,
                "qty": buy_qty_1,
                "order_type": "LOC",
                "desc": "Buy at 115% of avg (guaranteed)"
            })

        # Buy order 2: 50% at 100% (lower avg)
        buy_price_2 = round(avg_price * 1.00, 2)
        buy_budget_2 = daily_budget * 0.5
        buy_qty_2 = int(buy_budget_2 / buy_price_2)

        if buy_qty_2 > 0:
            result["orders"].append({
                "type": "buy",
                "price": buy_price_2,
                "qty": buy_qty_2,
                "order_type": "LOC",
                "desc": "Buy at 100% of avg (lower cost)"
            })

        # Sell order: all holdings at avg + profit
        sell_price = round(avg_price * (1 + sell_profit), 2)

        result["orders"].append({
            "type": "sell",
            "price": sell_price,
            "qty": qty,
            "order_type": "LOC",
            "desc": f"Sell all at {int(sell_profit*100)}% profit"
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
                ord_dv=order['type'],
                ctac_tlno="",
                mgco_aptm_odno="",
                ord_svr_dvsn_cd="0",
                ord_dvsn=LOC_ORDER_TYPE,  # "34" for LOC
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


def save_history(order_data: dict) -> bool:
    """
    Save order calculation to history file.

    Args:
        order_data: Result from calculate_order()

    Returns:
        bool: True if saved successfully
    """
    try:
        # Load existing history
        history = {"history": []}
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        history = json.loads(content)
            except (json.JSONDecodeError, IOError):
                pass

        # Append new entry
        history["history"].append(order_data)

        # Save
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=4, ensure_ascii=False)

        return True
    except Exception as e:
        print_log(PrintLevel.ERROR, f"Failed to save history: {e}")
        return False


def raoeo_menu():
    """RAOEO strategy menu interface."""
    os.system('cls' if os.name == 'nt' else 'clear')

    while True:
        # Instead of generic cls, we let render_ui and show_in_result_area handle the space
        render_ui(full_refresh=False)

        # Display menu in the top result area
        lines = [
            " [RAOEO Infinite Buying Strategy]",
            "",
            " 1. Calculate & Execute Orders",
            " 2. View History",
            " q. Back to Main Menu",
            "",
            "-" * 50 # Separator before input
        ]
        show_in_result_area(lines)

        choice = input_at(len(lines), 2, " Select: ").strip().lower()

        if choice == 'q':
            break

        elif choice == '1':
            # Calculate orders
            clear_result_area()
            show_in_result_area([" Calculating orders..."])

            result = calculate_order()

            if result.get('error'):
                show_in_result_area([f" Error: {result['error']}", "", " Press any key..."])
                msvcrt.getch()
                continue

            if not result['orders']:
                show_in_result_area([
                    f" [RAOEO Order Calculation - {result['date']}]",
                    f" State: {result['state'].upper()}",
                    "",
                    " No orders calculated for today.",
                    "",
                    " Press any key..."
                ])
                msvcrt.getch()
                continue

            # Display result
            display_lines = [
                f" [RAOEO Order Calculation - {result['date']}]",
                f" State: {result['state'].upper()}",
                f" Target: {result['config']['target']} @ {result['config']['exchange']}",
                f" Daily Budget: ${result['daily_budget']:.2f}",
                f" Holdings: {result['holdings']['qty']} shares @ ${result['holdings']['avg_price']:.2f}",
                f" Current Price: ${result['holdings']['cur_price']:.2f}",
                "",
                " Calculated Orders:"
            ]

            for i, order in enumerate(result['orders'], 1):
                display_lines.append(
                    f"   {i}. {order['type'].upper()} {order['qty']} @ ${order['price']:.2f} (LOC) - {order['desc']}"
                )

            display_lines.extend(["", " Place order? (y/N): "])
            show_in_result_area(display_lines)

            action = input_at(len(display_lines) + 1, 2, "").strip().lower()

            if action == 'y':
                # Execute
                show_in_result_area(display_lines[:-1] + [" Executing orders..."])
                exec_results = execute_orders(result['orders'], result['config'])

                # Show results
                result_lines = [" [Execution Results]", ""]
                for i, res in enumerate(exec_results, 1):
                    status = "SUCCESS" if res['success'] else f"FAILED: {res.get('error', 'Unknown')}"
                    order = res['order']
                    result_lines.append(f"   {i}. {order['type'].upper()} {order['qty']} @ ${order['price']:.2f} - {status}")

                # Auto-save history after execution
                save_history(result)
                result_lines.extend(["", " Session saved to history.", " Press any key..."])
                show_in_result_area(result_lines)

                msvcrt.getch()

            else:
                continue

        elif choice == '2':
            # View history with pagination and detailed table
            try:
                if not os.path.exists(HISTORY_FILE):
                    show_in_result_area([" No history found.", "", " Press any key..."])
                    msvcrt.getch()
                    continue

                with open(HISTORY_FILE, 'r', encoding='utf-8') as f_hist:
                    content = f_hist.read().strip()
                    if not content:
                        show_in_result_area([" History is empty.", "", " Press any key..."])
                        msvcrt.getch()
                        continue
                    history_data = json.loads(content)

                all_entries = history_data.get('history', [])
                if not all_entries:
                    show_in_result_area([" No entries in history.", "", " Press any key..."])
                    msvcrt.getch()
                    continue

                # Use reversed order to show most recent first
                entries = list(reversed(all_entries))
                offset = 0
                page_size = 5

                while True:
                    clear_result_area()
                    # Calculate pagination info
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

                        # Format orders: buy:3($47.55)
                        ord_strs = []
                        for o in entry.get('orders', []):
                            o_type = o.get('type', 'buy').lower()
                            o_qty = o.get('qty', 0)
                            o_prc = float(o.get('price', 0))
                            ord_strs.append(f"{o_type}:{o_qty}(${o_prc:.2f})")

                        orders_txt = ", ".join(ord_strs)
                        display_lines.append(f" {date} | {state} | {avg} | {cur} | {orders_txt}")

                    # Fill empty rows to maintain layout
                    for _ in range(page_size - len(page_entries)):
                        display_lines.append("")

                    display_lines.append(" " + "-" * 100)
                    display_lines.append(" (f) Next 5 items | (g) Back to Start | (q) Back to Menu")

                    show_in_result_area(display_lines)
                    # Move cursor below navigation hints (Row 13, Col 2)
                    sys.stdout.write("\033[13;2H")
                    sys.stdout.flush()

                    # Wait for navigation input
                    try:
                        ch = msvcrt.getch().decode('utf-8').lower()
                    except:
                        ch = ''

                    if ch == 'q':
                        break
                    elif ch == 'f':
                        offset += page_size
                        if offset >= total:
                            offset = 0 # Wrap around
                    elif ch == 'g':
                        offset = 0

            except Exception as e:
                show_in_result_area([f" Error reading history: {e}", "", " Press any key..."])
                msvcrt.getch()

    render_ui(full_refresh=True)
