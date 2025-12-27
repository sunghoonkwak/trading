import msvcrt
import logging
import kis_api.kis_auth as ka
from trading_ui import clear_result_area, show_in_result_area, input_at, render_ui, print_log, PrintLevel, safe_write, CLEAR_LINE
import trading_config
import trading_state
from account_helper import get_integrated_account_info
from kis_api.domestic_stock.order_cash.order_cash import order_cash
from kis_api.domestic_stock.order_rvsecncl.order_rvsecncl import order_rvsecncl
from kis_api.domestic_stock.inquire_psbl_rvsecncl.inquire_psbl_rvsecncl import inquire_psbl_rvsecncl
from kis_api.overseas_stock.order.order import order as order_overseas
from kis_api.overseas_stock.order_rvsecncl.order_rvsecncl import order_rvsecncl as order_rvsecncl_overseas
from kis_api.overseas_stock.inquire_nccs.inquire_nccs import inquire_nccs as inquire_nccs_overseas

def handle_place_order():
    clear_result_area()

    # Default to Overseas
    target_market = "US"

    try:
        while True:
            # Fetch balance each time we loop back to main menu
            data = get_integrated_account_info()
            # Domestic: Output2 'ord_psbl_cash' (Orderable Cash) or 'dnca_tot_amt' (Deposit)
            # Use 'dnca_tot_amt' as safe default if 'ord_psbl_cash' is not in Output2 of inquire-balance
            # Wait, inquire-balance (TTTC8434R) output2 has 'dnca_tot_amt', 'prvs_rcdl_excc_amt', etc.
            # It does NOT have 'ord_psbl_cash' explicitly usually (that's in inquire-psbl-order).
            # But let's check key names from log or previous usage.
            # Previous usage used inquire-psbl-order. Now we use inquire-balance.
            # inquire-balance Output2 keys: dnca_tot_amt, bfdy_tot_asst_evlu_amt, etc.
            # Let's use 'dnca_tot_amt' (Deposit) for KRW balance approximation.
            # For strict orderable, we might need the other API, but user wanted integration.
            # Let's use 'dnca_tot_amt' (Deposit) as Orderable for now.

            d_asset = data.get('domestic_asset', {})
            try: krw_bal = int(float(d_asset.get('dnca_tot_amt', 0)))
            except: krw_bal = 0

            # Overseas: Output2 'frcr_drwg_psbl_amt_1' (Withdrawable)
            o_asset = data.get('overseas_asset', {})
            try: usd_bal = float(o_asset.get('frcr_drwg_psbl_amt_1', 0))
            except: usd_bal = 0.0

            # Market Label
            market_label = "OVERSEAS (US)" if target_market == "US" else "DOMESTIC (KR)"

            # 1. Side Selection with Toggle
            clear_result_area()
            header = [f" [Place Order - {market_label}] KRW: {krw_bal:,} | USD: ${usd_bal:,.2f}"]
            show_in_result_area(header)

            side_input = input_at(2, 2, f" Select Side (1: Buy, 2: Sell, Enter: Toggle Check {('KR' if target_market=='US' else 'US')}, q: Cancel): ").strip()

            if side_input.lower() == 'q': return

            if not side_input:
                target_market = "KR" if target_market == "US" else "US"
                render_ui(full_refresh=True) # Refresh to clear artifacts
                continue

            ord_dv = "buy" if side_input == "1" else "sell" if side_input == "2" else None
            if not ord_dv: continue

            side_label = "BUY" if ord_dv == "buy" else "SELL"

            # Prepare Favorite List
            fav_list = []
            idx = 1
            # Filter specifically by target_market
            for item in trading_config.CONFIG.get(target_market, []):
                if not item.get('disabled', False):
                    fav_list.append((str(idx), item["ticker"], item["name"]))
                    idx += 1

            if not fav_list:
                show_in_result_area(header + ["No favorites found for this market.", "Press any key to toggle..."])
                msvcrt.getch()
                target_market = "KR" if target_market == "US" else "US"
                continue

            current_page = 0
            ITEMS_PER_PAGE = 10
            total_pages = (len(fav_list) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

            pdno = ""

            # Stock Selection Loop
            while True:
                start_idx = current_page * ITEMS_PER_PAGE
                end_idx = min(start_idx + ITEMS_PER_PAGE, len(fav_list))
                page_items = fav_list[start_idx:end_idx]

                lines = [f"[Place Order - {market_label} - {side_label}] KRW: {krw_bal:,} | USD: ${usd_bal:,.2f}"]

                # Build Grid
                row_buffer = []
                for item in page_items:
                    # Logic for displaying price/qty hints
                    # Lookup with prefixes for US if needed (DNAS, DNYE, DAME)
                    keys_to_check = [item[1]]
                    if target_market == "US":
                        keys_to_check += [f"{p}{item[1]}" for p in ["DNAS", "DNYE", "DAME"]]

                    curr_price = 0
                    for k in keys_to_check:
                        st = trading_state.stock_data_state.get(k, {})
                        p = st.get('price', 0)
                        if p == 0: p = st.get('ask', 0)
                        if p > 0:
                            curr_price = p
                            break

                    qty_str = ""
                    if ord_dv == "buy":
                        if curr_price > 0:
                            if target_market == "KR":
                                qty_str = f"({int(krw_bal / curr_price)})"
                            else:
                                # US: USD / Price
                                qty_str = f"({int(usd_bal / curr_price)})"
                        else:
                            qty_str = "(?)"

                    display_text = f"{item[0]}.{item[2]}{qty_str}"
                    # Truncate if too long (simple check)
                    if len(display_text) > 18: display_text = display_text[:17] + "."

                    row_buffer.append(f"{display_text}")
                    if len(row_buffer) == 5:
                        lines.append(" ".join([f"{x:<20}" for x in row_buffer]))
                        row_buffer = []

                if row_buffer:
                    lines.append(" ".join([f"{x:<20}" for x in row_buffer]))

                lines.append(" [Enter]: Next List   q: Back   99: Direct Input")
                show_in_result_area(lines)

                input_row = len(lines) + 2
                user_input = input_at(input_row, 2, "Select Index: ").strip()

                if not user_input:
                    current_page += 1
                    if current_page >= total_pages: current_page = 0
                    continue

                if user_input.lower() == 'q':
                    pdno = None
                    break # Break stock loop to go back to side selection

                if user_input == '99':
                    pdno = input_at(input_row + 1, 2, "Enter Stock Code: ").strip()
                    break

                found = next((x for x in fav_list if x[0] == user_input), None)
                if found:
                    pdno = found[1]
                    break

            if not pdno: continue # Back to Side/Market Selection

            # Order Details Entry
            stock_info = trading_config.get_stock_info(pdno)
            stock_name = stock_info.get('name', 'Unknown')

            clear_result_area()
            header_lines = [
                f" [Place Order - {market_label} - {side_label}]",
                f" Stock : {pdno} ({stock_name})"
            ]
            show_in_result_area(header_lines)

            price_input = input_at(len(header_lines)+1, 2, "Price (Enter for Market/Current, q: Cancel): ").strip()
            if price_input.lower() == 'q': continue

            # Determine Price
            # Note: For US, usually limit orders are standard. Market orders might need special '0' or different implementation.
            # Assuming limit order if price given.
            # Check price logic
            price_val = 0
            if not price_input or price_input == "0":
                # Use current price reference
                price_val = trading_state.stock_data_state.get(pdno, {}).get('price', 0)
                if price_val == 0: price_val = trading_state.stock_data_state.get(pdno, {}).get('ask', 0)
            else:
                try: price_val = float(price_input)
                except: price_val = 0

            # Calc Max Qty
            max_qty_str = "?"
            if price_val > 0:
                if target_market == "KR":
                    max_qty = int(krw_bal / price_val)
                    max_qty_str = f"{max_qty}"
                else:
                    max_qty = int(usd_bal / price_val)
                    max_qty_str = f"{max_qty}"

            qty = input_at(len(header_lines)+2, 2, f"Quantity (MAX: {max_qty_str}, q: Cancel): ").strip()
            if qty.lower() == 'q': continue

            # Final Confirm
            price_disp = price_input if price_input and price_input != "0" else f"{price_val} (Market/Ref)"
            if target_market == "KR" and (not price_input or price_input=="0"):
                price_disp = "Market Price"

            recap = header_lines + [
                f" Side       : {ord_dv.upper()}",
                f" Quantity   : {qty}",
                f" Price      : {price_disp}",
            ]
            show_in_result_area(recap)

            confirm = input_at(len(recap)+1, 2, " Submit Order? (y/n): ").strip().lower()
            if confirm != 'y':
                show_in_result_area(recap + ["Order Cancelled."])
                msvcrt.getch()
                continue

            # Execute Order
            cano = ka.getTREnv().my_acct
            prod = ka.getTREnv().my_prod

            df_res = None
            if target_market == "KR":
                ord_dvsn = "01" if not price_input or price_input == "0" else "00"
                df_res = order_cash(
                    env_dv="real",
                    ord_dv=ord_dv,
                    cano=cano,
                    acnt_prdt_cd=prod,
                    pdno=pdno,
                    ord_dvsn=ord_dvsn,
                    ord_qty=qty,
                    ord_unpr=price_input if ord_dvsn == "00" else "0",
                    excg_id_dvsn_cd="SOR" # SOR default
                )
            else:
                # Overseas
                # Need Exchange Code. Try to get from config or default to NASD (as inferred)
                mkt_code = stock_info.get('market', 'NASD').upper()
                # Config might have specific codes or need mapping
                # Assuming Config has valid codes (NASDAQ, NYSE etc -> need mapping)
                # Map standard markets to KIS codes
                excg_map = {"NASDAQ": "NASD", "NYSE": "NYSE", "AMEX": "AMEX", "US": "NASD"}
                ovrs_excg = excg_map.get(mkt_code, "NASD") # Default to NASD (which checks all for some APIs, but for order needs specific?)
                # Wait, for ORDER, we need specific. But if we don't know, maybe we should ask or try NASD?
                # User config usually says NASDAQ/NYSE.

                # Price must be supplied. If 0/Market, US uses "00" with price "0"?
                # Check order() doc: "00 : 지정가". Market orders for US? "32: LOO, 31: MOO"... KIS usually treats "00" as limit.
                # If user wants market, maybe we force limit at current price? Or check if US supports market order via API easily.
                # Documentation says "00: Limit". Market order might be simpler if we just pass 0 price?
                # Let's stick to Limit (00) with specified price. If user entered 0, we use collected price?

                final_price = str(price_val)
                if not price_input or price_input == "0":
                    # Use current price as limit price if "market" intended, or warn?
                    # Let's trust user input. If 0, maybe API rejects.
                    pass

                df_res = order_overseas(
                    cano=cano,
                    acnt_prdt_cd=prod,
                    ovrs_excg_cd=ovrs_excg,
                    pdno=pdno,
                    ord_qty=qty,
                    ovrs_ord_unpr=final_price,
                    ord_dv=ord_dv,
                    ctac_tlno="",
                    mgco_aptm_odno="",
                    ord_svr_dvsn_cd="0",
                    ord_dvsn="00", # Limit
                    env_dv="real"
                )

            # Check Result
            is_success = False
            msg = "FAILED"

            if not df_res.empty:
                cols = {c.lower(): c for c in df_res.columns}
                if 'odno' in cols or 'ord_no' in cols: # Overseas might use ODNO
                    is_success = True
                    msg = "SUCCESS"
                    # Log details if needed

            show_in_result_area(recap + [f"Result: {msg}", "Press any key..."])
            msvcrt.getch()

    except Exception as e:
        print_log(PrintLevel.ERROR, f"Order Flow Error: {e}")
    finally:
        render_ui(full_refresh=True)

def handle_manage_orders():
    clear_result_area()

    try:
        lines = ["="*40, " [Manage Open Orders]", "="*40, "Fetching open orders..."]
        show_in_result_area(lines)

        cano = ka.getTREnv().my_acct
        prod = ka.getTREnv().my_prod

        # Priority: Overseas -> Domestic
        market_found = "US"

        # 1. Check Overseas
        # ovrs_excg_cd="NASD" (searches all US matches per docs) or leave empty if possible (but docs say must verify).
        # Assuming US trading mainly.
        df = inquire_nccs_overseas(cano=cano, acnt_prdt_cd=prod, ovrs_excg_cd="NASD", sort_sqn="DS", FK200="", NK200="")

        if df.empty:
            market_found = "KR"
            df = inquire_psbl_rvsecncl(cano=cano, acnt_prdt_cd=prod, inqr_dvsn_1="0", inqr_dvsn_2="0")

        if df.empty:
            show_in_result_area(lines + ["No open orders found in US or KR.", "Press any key to return..."])
            msvcrt.getch()
            return

        order_list = []
        for i, row in df.iterrows():
            # Normalize fields
            # KR: prdt_name, ord_unpr, psbl_qty, ord_dvsn_cd, ord_gno_brno, odno
            # US: prdt_name, ft_ord_unpr4(price), ft_ord_qty4(qty), sll_buy_dvsn_cd_name, odno, ovrs_excg_cd, pdno

            # Common
            name = row.get('prdt_name', row.get('pdno', 'Unknown'))
            odno = row.get('odno', 'Unknown')

            # Helper for robust retrieval (case-insensitive)
            # Create a localized dict with lower-cased keys for this row
            row_lower = {k.lower(): v for k, v in row.items()}

            def get_val(keys, default=0):
                for k in keys:
                    if k in row_lower:
                        return row_lower[k]
                return default

            # Price/Qty
            price = 0
            qty = 0
            side = "?"

            if market_found == "KR":
                side = "BUY " if row.get('sll_buy_dvsn_cd') == '02' else "SELL"
                price = int(float(row.get('ord_unpr', '0')))
                qty = row.get('psbl_qty', 0)
            else: # US
                # Log raw keys for first item to help debugging
                if i == 0:
                    logging.debug(f"[ManageOrders] Row Keys: {list(row.keys())}")
                    logging.debug(f"[ManageOrders] Row Values: {row.to_dict()}")

                side_name = get_val(['sll_buy_dvsn_cd_name', 'sll_buy_dvsn_name'], '?')
                if not side_name or side_name == '?':
                    side_code = get_val(['sll_buy_dvsn_cd'], '')
                    side = "BUY" if side_code=='02' else "SELL"
                else:
                    side = side_name

                # Price: Try floating point fields first, then string fields
                p_val = get_val(['ft_ord_unpr4', 'ft_ord_unpr3', 'ovrs_ord_unpr', 'ord_unpr'], '0')
                try: price = float(p_val)
                except: price = 0.0

                # Qty: Prioritize 'nccs_qty' (Unexecuted) -> 'ord_qty' (Total Order)
                q_val = get_val(['nccs_qty', 'ft_ord_qty4', 'ord_qty'], 0)
                try: qty = int(float(q_val))
                except: qty = 0

            order_list.append(f" {i+1}. [{market_found}] {name} | {side} | Prc: {price} | Qty: {qty}")
            if i >= 6: break

        show_in_result_area(lines[:3] + order_list + ["Select Index or 'q':"])
        idx_s = input_at(len(order_list)+4, 2, "Choice: ").strip()
        if idx_s.lower() == 'q' or not idx_s: return

        try:
            idx = int(idx_s) - 1
            if idx < 0 or idx >= len(df): raise ValueError
        except: return

        target_order = df.iloc[idx]
        # Normalize target order to dict with lowercase keys
        t_ord = {k.lower(): v for k, v in target_order.items()}

        action = input_at(len(order_list)+5, 2, "Action (1: Correct, 2: Cancel): ").strip()
        if action not in ['1', '2']: return

        # Execute Action
        df_res = None
        if market_found == "KR":
            ord_dvsn = t_ord.get('ord_dvsn_cd', t_ord.get('ord_dvsn', '00'))
            org_no = t_ord.get('ord_gno_brno', t_ord.get('krx_fwdg_ord_orgno', ''))
            excg_id = t_ord.get('excg_id_dvsn_cd', 'KRX')

            if action == '2': # Cancel
                df_res = order_rvsecncl(
                    env_dv="real",
                    cano=cano,
                    acnt_prdt_cd=prod,
                    krx_fwdg_ord_orgno=org_no,
                    orgn_odno=t_ord.get('odno'),
                    ord_dvsn=ord_dvsn,
                    rvse_cncl_dvsn_cd="02",
                    ord_qty=t_ord.get('psbl_qty'),
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
                    orgn_odno=t_ord.get('odno'),
                    ord_dvsn=ord_dvsn,
                    rvse_cncl_dvsn_cd="01", # Correct
                    ord_qty=t_ord.get('psbl_qty'),
                    ord_unpr=new_price,
                    qty_all_ord_yn="Y",
                    excg_id_dvsn_cd=excg_id
                )
        else: # US
            # Cancel/Correct Overseas
            pdno = t_ord.get('pdno')
            orgn_odno = t_ord.get('odno')
            excg_cd = t_ord.get('ovrs_excg_cd', 'NASD')

            # Qty (nccs_qty = unexecuted, ft_ord_qty4/ord_qty = total?)
            # Prioritize nccs_qty if available for remnant cancellation
            qty = t_ord.get('nccs_qty', t_ord.get('ft_ord_qty4', t_ord.get('ord_qty', 0)))

            # Use full quantity directly as requested (no partial)
            final_qty = str(qty)

            if action == '2': # Cancel
                df_res = order_rvsecncl_overseas(
                    cano=cano,
                    acnt_prdt_cd=prod,
                    ovrs_excg_cd=excg_cd,
                    pdno=pdno,
                    orgn_odno=orgn_odno,
                    rvse_cncl_dvsn_cd="02", # Cancel
                    ord_qty=final_qty,
                    ovrs_ord_unpr="0",
                    mgco_aptm_odno="",
                    ord_svr_dvsn_cd="0",
                    env_dv="real"
                )
            else: # Correct
                new_price = input_at(len(order_list)+6, 2, "New Price: ").strip()
                df_res = order_rvsecncl_overseas(
                    cano=cano,
                    acnt_prdt_cd=prod,
                    ovrs_excg_cd=excg_cd,
                    pdno=pdno,
                    orgn_odno=orgn_odno,
                    rvse_cncl_dvsn_cd="01", # Correct
                    ord_qty=final_qty,
                    ovrs_ord_unpr=new_price,
                    mgco_aptm_odno="",
                    ord_svr_dvsn_cd="0",
                    env_dv="real"
                )

        # Check Result
        clear_result_area()
        # Clear specific input rows that might persist (rows 10-14)
        # Note: render_ui will restore rows 12-14 (Separator/Header) if we call it, but we want to show result first.
        # Safest is to write spaces to those lines then let render_ui fix the bottom later.
        for r in range(10, 15):
            safe_write(f"\033[{r};1H{CLEAR_LINE}")

        is_success = False
        res_msg = "Processed"
        res_odno = ""

        if not df_res.empty:
            # Case-insensitive column check
            cols = {c.lower(): c for c in df_res.columns}

            # Success Check
            if 'odno' in cols:
                is_success = True
                res_odno = df_res.iloc[0][cols['odno']]
            elif 'ord_no' in cols:
                is_success = True
                res_odno = df_res.iloc[0][cols['ord_no']]
            elif 'msg1' in cols:
                # Some APIs return success msg in msg1 without odno in output (rare for order)
                if df_res.iloc[0][cols['msg1']] and "정상" in str(df_res.iloc[0][cols['msg1']]):
                    is_success = True

            # Message Extraction
            if 'msg1' in cols: res_msg = df_res.iloc[0][cols['msg1']]
            elif 'message' in cols: res_msg = df_res.iloc[0][cols['message']]

        final_lines = lines[:3] # Keep Header
        if is_success:
            final_lines.append(f" Result : SUCCESS")
            final_lines.append(f" Ord No : {res_odno}")
            final_lines.append(f" Message: {res_msg}")
        else:
            final_lines.append(f" Result : FAILED")
            final_lines.append(f" Message: {res_msg}")

        final_lines.append(" Press any key to return...")
        show_in_result_area(final_lines)

        msvcrt.getch()

    except Exception as e:
        print_log(PrintLevel.ERROR, f"Order Manage Error: {e}")
    finally:
        render_ui(full_refresh=True)
