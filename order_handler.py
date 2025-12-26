import msvcrt
import logging
import kis_api.kis_auth as ka
from trading_ui import clear_result_area, show_in_result_area, input_at, render_ui, print_log, PrintLevel
import trading_config
import trading_state
from account_helper import get_account_balance
from kis_api.domestic_stock.order_cash.order_cash import order_cash
from kis_api.domestic_stock.order_rvsecncl.order_rvsecncl import order_rvsecncl
from kis_api.domestic_stock.inquire_psbl_rvsecncl.inquire_psbl_rvsecncl import inquire_psbl_rvsecncl

def handle_place_order():
    clear_result_area()

    try:
        # Fetch balance initially
        bal = get_account_balance()
        krw_bal = bal.get('krw_orderable', 0)
        usd_bal = bal.get('usd_withdrawable', 0.0)

        # Prepare Favorite List (Flatten version for selection menu)
        fav_list = []
        idx = 1
        for market in ["KR", "US"]:
            for item in trading_config.CONFIG.get(market, []):
                if not item.get('disabled', False):
                    # item format: {"ticker": "...", "name": "...", "color": [...], "disabled": bool}
                    fav_list.append((str(idx), item["ticker"], item["name"]))
                    idx += 1

        current_page = 0
        ITEMS_PER_PAGE = 10
        total_pages = (len(fav_list) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if fav_list else 1

        side_input = input_at(2, 2, "Select Side (1: Buy, 2: Sell, q: Cancel): ").strip()
        if not side_input or side_input.lower() == 'q': return
        ord_dv = "buy" if side_input == "1" else "sell"
        side_label = "BUY" if ord_dv == "buy" else "SELL"

        pdno = ""

        while True:
            # 1. Build Menu UI
            start_idx = current_page * ITEMS_PER_PAGE
            end_idx = min(start_idx + ITEMS_PER_PAGE, len(fav_list))
            page_items = fav_list[start_idx:end_idx]

            # Header with Balance
            # Header with Balance
            lines = [f"[Place Domestic Cash Order - {side_label}] KRW: {krw_bal:,} , USD: ${usd_bal:,.2f}"]
            # lines.append("-" * 100)

            # Build Grid: 5 items per line
            row_buffer = []
            for item in page_items:
                # item: (idx, code, name)
                # Format: '1.Name' truncated or padded to ~15 chars
                # Calculate max buyable qty
                state = trading_state.stock_data_state.get(item[1], {})
                curr_price = state.get('price', 0)
                if curr_price == 0:
                    curr_price = state.get('ask', 0)

                # Max Qty Calculation (Only for Buy)
                qty_str = ""
                if ord_dv == "buy":
                    if curr_price > 0:
                        qty_str = f"({int(krw_bal / curr_price)}주)"
                    else:
                        qty_str = "(nodata)"

                display_text = f"{item[0]}.{item[2]}{qty_str}"
                row_buffer.append(f"{display_text}")

                if len(row_buffer) == 5:
                    lines.append(" ".join([f"{x:<18}" for x in row_buffer]))
                    row_buffer = []

            if row_buffer:
                 lines.append(" ".join([f"{x:<18}" for x in row_buffer]))

            # lines.append("-" * 100)
            lines.append(" [Enter]: Next List   q: Cancel   99: Direct Input")

            # Pad lines to ensure we overwrite previous output (anti-ghosting)
            # Padding removed to prevent log overlap

            show_in_result_area(lines)

            # 2. Input
            # Calculate input row relative to lines we just printed
            # Use a safe fixed row if lines fluctuates, or strictly following len(lines)
            # lines has been padded to 12, so input at 16 (12 + 4) is safe
            input_row = len(lines) + 1
            user_input = input_at(input_row, 2, "Select Index: ").strip()

            # Clear the input line for next iteration just in case (optional as input_at clears line)

            # Navigation Logic
            if not user_input:
                current_page += 1
                if current_page >= total_pages:
                    current_page = 0
                continue

            if user_input == '0' or user_input.lower() == 'q':
                return

            if user_input == '99':
                pdno = input_at(input_row + 1, 2, "Enter Stock Code: ").strip()
                break

            # Check if selected from list
            found = next((x for x in fav_list if x[0] == user_input), None)
            if found:
                pdno = found[1]
                break

            # Check if direct code input (fallback)
            if len(user_input) >= 6:
                pdno = user_input
                break

            # Loop again if invalid
            continue

        if not pdno: return

        # Stock Name Lookup
        stock_name = trading_config.get_stock_info(pdno).get('name', 'Unknown')

        # Redraw header with selected stock info
        clear_result_area()
        header_lines = [
            f" [Place Domestic Cash Order - {side_label}]",
            # "-"*80,
            f" Stock Code : {pdno}",
            f" Stock Name : {stock_name}"
        ]
        show_in_result_area(header_lines)

        # Side is already selected
        # side_idx = input_at(len(header_lines)+2, 2, "Side (1: Buy, 2: Sell, q: Cancel): ").strip() # Removed

        price_input = input_at(len(header_lines)+1, 2, "Price (Enter for Market, q: Cancel): ").strip()
        if price_input.lower() == 'q': return

        # Calculate Max Qty logic
        max_qty_str = "?"
        calc_price = 0

        # If market price or price not entered, use current price from state
        if not price_input or price_input == "0":
            calc_price = trading_state.stock_data_state.get(pdno, {}).get('price', 0)
        else:
            try:
                calc_price = int(price_input)
            except:
                calc_price = 0

        if calc_price > 0:
            max_qty = int(krw_bal / calc_price)
            max_qty_str = f"{max_qty}"

        qty = input_at(len(header_lines)+2, 2, f"Quantity (MAX: {max_qty_str}주, q: Cancel): ").strip()
        if qty.lower() == 'q': return
        price = price_input  # Keep variable name consistent with downstream logic

        # Final Formatting
        ord_dvsn = "01" if not price or price == "0" else "00"

        recap = header_lines + [
            f" Side       : {ord_dv.upper()}",
            f" Quantity   : {qty}",
            f" Price      : {'Market' if ord_dvsn == '01' else f'{int(price):,}'}",
            # "-"*80
        ]
        show_in_result_area(recap)

        confirm = input_at(len(recap)+1, 2, " Submit Order? (y/n): ").strip().lower()
        if confirm != 'y':
            show_in_result_area(recap + ["Order Cancelled. Press any key..."])
            msvcrt.getch()
            return

        cano = ka.getTREnv().my_acct
        prod = ka.getTREnv().my_prod

        df = order_cash(
            env_dv="real",
            ord_dv=ord_dv,
            cano=cano,
            acnt_prdt_cd=prod,
            pdno=pdno,
            ord_dvsn=ord_dvsn,
            ord_qty=qty,
            ord_unpr=price if ord_dvsn == "00" else "0",
            excg_id_dvsn_cd="SOR"
        )

        # Robust field retrieval (casing varies across KIS APIs)
        odno_val = None
        ord_tmd_val = None
        if not df.empty:
            cols = {c.lower(): c for c in df.columns}
            if 'odno' in cols:
                odno_val = df.iloc[0].get(cols['odno'])
            if 'ord_tmd' in cols:
                ord_tmd_val = df.iloc[0].get(cols['ord_tmd'])

        if odno_val:
            res_lines = [
                # "-"*80,
                "Result: SUCCESS",
                f"Order No: {odno_val}",
                f"Time: {ord_tmd_val if ord_tmd_val else 'N/A'}",
                "Press any key to return..."
            ]
        else:
            res_lines = ["-"*80, "Result: FAILED (Check logs)", "Press any key to return..."]

        show_in_result_area(recap + res_lines)
        msvcrt.getch()

    except Exception as e:
        print_log(PrintLevel.ERROR, f"Order error: {e}")
    finally:
        render_ui(full_refresh=True)

def handle_manage_orders():
    clear_result_area()

    try:
        lines = ["="*40, " [Manage Open Orders]", "="*40, "Fetching open orders..."]
        show_in_result_area(lines)

        cano = ka.getTREnv().my_acct
        prod = ka.getTREnv().my_prod

        df = inquire_psbl_rvsecncl(cano=cano, acnt_prdt_cd=prod, inqr_dvsn_1="0", inqr_dvsn_2="0")

        # [DEBUG] Dump raw data for troubleshooting
        if not df.empty:
            logging.debug(f"--- Raw Open Orders Data ---\n{df.to_dict(orient='records')}")

        if df.empty:
            show_in_result_area(lines + ["No open orders found.", "Press any key to return..."])
            msvcrt.getch()
            return

        # List orders
        order_list = []
        for i, row in df.iterrows():
            # KIS API for inquire-psbl-rvsecncl uses 'prdt_name' not 'itms_nm'
            name = row.get('prdt_name', row.get('pdno', 'Unknown'))
            side = "BUY " if row.get('sll_buy_dvsn_cd') == '02' else "SELL"
            price = int(float(row.get('ord_unpr', '0')))
            order_list.append(f" {i+1}. {name} | {side} | Prc: {price:,} | Qty: {row['psbl_qty']}")
            if i >= 5: break # Only show first 5

        show_in_result_area(lines[:3] + order_list + ["Select Index or 'q':"])
        idx_s = input_at(len(order_list)+4, 2, "Choice: ").strip()
        if idx_s.lower() == 'q' or not idx_s: return

        idx = int(idx_s) - 1
        target_order = df.iloc[idx]

        action = input_at(len(order_list)+5, 2, "Action (1: Correct, 2: Cancel): ").strip()

        # Use existing ord_dvsn_cd if available, else fallback to '00'
        ord_dvsn = target_order.get('ord_dvsn_cd', target_order.get('ord_dvsn', '00'))
        # KIS API for inquire-psbl-rvsecncl uses 'ord_gno_brno' for organization number
        org_no = target_order.get('ord_gno_brno', target_order.get('krx_fwdg_ord_orgno', ''))
        # Dynamically get Exchange ID (Crucial: orders might be SOR/NXT, not just KRX)
        excg_id = target_order.get('excg_id_dvsn_cd', 'KRX')

        if action == '2': # Cancel
            df_res = order_rvsecncl(
                env_dv="real",
                cano=cano,
                acnt_prdt_cd=prod,
                krx_fwdg_ord_orgno=org_no,
                orgn_odno=target_order['odno'],
                ord_dvsn=ord_dvsn,
                rvse_cncl_dvsn_cd="02",
                ord_qty=target_order['psbl_qty'],
                ord_unpr="0",
                qty_all_ord_yn="Y",
                excg_id_dvsn_cd=excg_id
            )
        else: # Correct
            new_price = input_at(len(order_list)+6, 2, "New Price: ").strip()
            df_res = order_rvsecncl(
                env_dv="real",
                cano=cano,
                acnt_prdt_cd=prod,
                krx_fwdg_ord_orgno=org_no,
                orgn_odno=target_order['odno'],
                ord_dvsn=ord_dvsn,
                rvse_cncl_dvsn_cd="01",
                ord_qty=target_order['psbl_qty'],
                ord_unpr=new_price,
                qty_all_ord_yn="Y",
                excg_id_dvsn_cd=excg_id
            )

        # Robust field retrieval for modification/cancellation result
        res_odno = None
        if not df_res.empty:
            cols = {c.lower(): c for c in df_res.columns}
            if 'odno' in cols:
                res_odno = df_res.iloc[0].get(cols['odno'])

        if res_odno:
            show_in_result_area(lines[:3] + ["Result: SUCCESS", f"Order/Req No: {res_odno}", "Press any key to return..."])
        else:
            # Check for specific error message
            err_msg = "Check logs"
            if 'error_msg' in df_res.columns and not df_res.empty:
                err_msg = df_res.iloc[0]['error_msg']
            show_in_result_area(lines[:3] + [f"Result: FAILED ({err_msg})", "Press any key to return..."])

        msvcrt.getch()

    except Exception as e:
        print_log(PrintLevel.ERROR, f"Order error: {e}")
    finally:
        render_ui(full_refresh=True)
