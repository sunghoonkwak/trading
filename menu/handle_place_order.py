"""
This module handles the order placement workflow for KR and US markets.
It provides an interactive interface for market selection, stock picking, and price/quantity input.
"""
import logging
from utils import getch
from kis.kis_api import kis_auth as ka
from display import show_in_result_area, input_at, add_alert
import trading_config
import trading_state
from .menu import MENU_DEBUG
from data.data_service import get_portfolio_data
from kis.kis_api.domestic_stock.order_cash.order_cash import order_cash
from kis.kis_api.overseas_stock.order.order import order as order_overseas

def fetch_balances():
    """Retrieve current KRW and USD balances via data_service."""
    portfolio = get_portfolio_data(silent=True)
    if portfolio.get('error'):
        return 0, 0.0

    stats = portfolio.get('stats', {})
    krw_bal = stats.get('kr_cash_krw', 0)
    usd_bal = stats.get('us_cash_usd', 0.0)
    return krw_bal, usd_bal

def fetch_stock_price(pdno):
    """Get current/last price for a specific stock ticker, handling market prefixes."""
    pdno_upper = pdno.upper()

    # 1. Precise match first (case-insensitive)
    for key in trading_state.stock_data_state:
        if key.upper() == pdno_upper:
            data = trading_state.stock_data_state[key]
            price = data.get('price', 0)
            return price if price > 0 else data.get('ask', 0)

    # 2. Search with prefix/contains (e.g., SOXL -> DNASSOXL)
    for key, data in trading_state.stock_data_state.items():
        if pdno_upper in key.upper():
            price = data.get('price', 0)
            return price if price > 0 else data.get('ask', 0)

    return 0

def execute_place_order(target_market, ord_dv, pdno, qty, price_input, price_val):
    """Call KIS API to execute the trade."""
    cano = ka.getTREnv().my_acct
    prod = ka.getTREnv().my_prod

    if MENU_DEBUG:
        logging.debug(f"[MenuDebug] Place Order - Mkt: {target_market}, Side: {ord_dv}, Symbol: {pdno}, Qty: {qty}, PriceIn: {price_input}")

    if target_market == "KR":
        ord_dvsn = "01" if not price_input or price_input == "0" else "00"
        return order_cash(
            env_dv="real", ord_dv=ord_dv, cano=cano, acnt_prdt_cd=prod,
            pdno=pdno, ord_dvsn=ord_dvsn, ord_qty=qty,
            ord_unpr=price_input if ord_dvsn == "00" else "0",
            excg_id_dvsn_cd="SOR"
        )
    else:
        # Overseas
        stock_info = trading_config.get_stock_info(pdno)
        mkt_code = stock_info.get('market', 'NASD').upper()
        excg_map = {"NASDAQ": "NASD", "NYSE": "NYSE", "AMEX": "AMEX", "US": "NASD"}
        ovrs_excg = excg_map.get(mkt_code, "NASD")

        return order_overseas(
            cano=cano, acnt_prdt_cd=prod, ovrs_excg_cd=ovrs_excg, pdno=pdno,
            ord_qty=qty, ovrs_ord_unpr=str(price_val), ord_dv=ord_dv,
            ctac_tlno="", mgco_aptm_odno="", ord_svr_dvsn_cd="0",
            ord_dvsn="00", env_dv="real"
        )

def handle_place_order():
    """Main menu controller for placing orders."""
    target_market = "US"

    try:
        while True:
            krw_bal, usd_bal = fetch_balances()
            market_label = "OVERSEAS (US)" if target_market == "US" else "DOMESTIC (KR)"

            # 1. Side Selection
            header = [f" [Place Order - {market_label}] Orderable KRW: {krw_bal:,} | USD: ${usd_bal:,.2f}"]
            show_in_result_area(header)

            side_input = input_at(2, 2, f" Select Side (1: Buy, 2: Sell, Enter: Toggle Check {('KR' if target_market=='US' else 'US')}, q: Cancel): ").strip()
            if side_input.lower() == 'q': return
            if not side_input:
                target_market = "KR" if target_market == "US" else "US"
                continue

            ord_dv = "buy" if side_input == "1" else "sell" if side_input == "2" else None
            if not ord_dv: continue
            side_label = "BUY" if ord_dv == "buy" else "SELL"

            # 2. Stock Selection
            fav_list = []
            idx = 1
            for item in trading_config.CONFIG.get(target_market, []):
                if not item.get('disabled', False):
                    fav_list.append((str(idx), item["ticker"], item["name"]))
                    idx += 1

            if not fav_list:
                show_in_result_area(header + ["No favorites found for this market.", "Press any key to toggle..."])
                getch()
                target_market = "KR" if target_market == "US" else "US"
                continue

            current_page = 0
            ITEMS_PER_PAGE = 10
            total_pages = (len(fav_list) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

            pdno = ""
            while True:
                start_idx = current_page * ITEMS_PER_PAGE
                end_idx = min(start_idx + ITEMS_PER_PAGE, len(fav_list))
                page_items = fav_list[start_idx:end_idx]

                lines = [f"[Place Order - {market_label} - {side_label}] Orderable KRW: {krw_bal:,} | USD: ${usd_bal:,.2f}"]
                row_buffer = []
                for item in page_items:
                    curr_price = fetch_stock_price(item[1])
                    qty_str = ""
                    if ord_dv == "buy":
                        if curr_price > 0:
                            qty_str = f"({int((krw_bal if target_market=='KR' else usd_bal) / curr_price)})"
                        else: qty_str = "(?)"

                    display_text = f"{item[0]}.{item[2]}{qty_str}"
                    if len(display_text) > 18: display_text = display_text[:17] + "."
                    row_buffer.append(f"{display_text}")
                    if len(row_buffer) == 5:
                        lines.append(" ".join([f"{x:<20}" for x in row_buffer]))
                        row_buffer = []

                if row_buffer: lines.append(" ".join([f"{x:<20}" for x in row_buffer]))
                lines.append(" [Enter]: Next List   q: Back   99: Direct Input")
                show_in_result_area(lines)

                user_input = input_at(len(lines) + 2, 2, "Select Index: ").strip()
                if not user_input:
                    current_page = (current_page + 1) % total_pages
                    continue
                if user_input.lower() == 'q':
                    pdno = None
                    break
                if user_input == '99':
                    pdno = input_at(len(lines) + 3, 2, "Enter Stock Code: ").strip()
                    break
                found = next((x for x in fav_list if x[0] == user_input), None)
                if found:
                    pdno = found[1]
                    break

            if not pdno: continue

            # 3. Details and Confirm
            stock_info = trading_config.get_stock_info(pdno)
            stock_name = stock_info.get('name', 'Unknown')
            curr_price = fetch_stock_price(pdno)

            header_lines = [
                f" [Place Order - {market_label} - {side_label}]",
                f" Stock : {pdno} ({stock_name})",
                f" Current Price: {f'${curr_price:,.2f}' if target_market == 'US' else f'{curr_price:,.0f} KRW' if curr_price > 0 else 'Waiting for data...'}"
            ]
            show_in_result_area(header_lines)

            price_input = input_at(len(header_lines)+1, 2, "Price (Enter for Market/Current, q: Cancel): ").strip()
            if price_input.lower() == 'q': continue

            price_val = 0
            if not price_input or price_input == "0":
                price_val = fetch_stock_price(pdno)
                msg = f" Market Price: {price_val} | Use this price? (y/n, q: Cancel): "
                price_confirm = input_at(len(header_lines)+2, 2, msg).strip().lower()
                if price_confirm == 'q': return
                if price_confirm != 'y': continue
                offset = 3
            else:
                try: price_val = float(price_input)
                except: price_val = 0
                offset = 2

            max_qty_str = f"{int((krw_bal if target_market=='KR' else usd_bal) / price_val)}" if price_val > 0 else "?"
            qty = input_at(len(header_lines)+offset, 2, f"Quantity (MAX: {max_qty_str}, q: Cancel): ").strip()
            if qty.lower() == 'q': continue

            price_disp = price_input if price_input and price_input != "0" else f"{price_val} (Market/Ref)"
            if target_market == "KR" and (not price_input or price_input=="0"): price_disp = "Market Price"

            recap = header_lines + [f" Side       : {ord_dv.upper()}", f" Quantity   : {qty}", f" Price      : {price_disp}"]
            show_in_result_area(recap)

            confirm = input_at(len(recap)+1, 2, " Submit Order? (y/n): ").strip().lower()
            if confirm != 'y':
                show_in_result_area(recap + ["Order Cancelled."])
                getch()
                continue

            # 4. Execution
            df_res, err_msg = execute_place_order(target_market, ord_dv, pdno, qty, price_input, price_val)

            # Result Check
            is_success = False
            if not df_res.empty:
                cols = {c.lower(): c for c in df_res.columns}
                if 'odno' in cols or 'ord_no' in cols:
                    is_success = True

            result_txt = "SUCCESS" if is_success else f"FAILED: {err_msg if err_msg else 'Unknown Error'}"
            show_in_result_area(recap + [f"Result: {result_txt}", "Press any key..."])
            getch()

    except Exception as e:
        add_alert(f"Order Flow Error: {e}", "ERROR")
