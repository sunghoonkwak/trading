"""
This module handles the management of open orders (cancellation and correction).
It follows a strict 6-step workflow for user interaction and API execution.
"""
import msvcrt
import logging
import kis_api.kis_auth as ka
import trading_config
from display import clear_result_area, show_in_result_area, input_at, render_ui, PrintLevel, print_log, safe_write, CLEAR_LINE, update_order_state, add_alert, clear_order_states
from .menu import MENU_DEBUG
from kis_api.domestic_stock.order_rvsecncl.order_rvsecncl import order_rvsecncl
from kis_api.domestic_stock.inquire_psbl_rvsecncl.inquire_psbl_rvsecncl import inquire_psbl_rvsecncl
from kis_api.overseas_stock.order_rvsecncl.order_rvsecncl import order_rvsecncl as order_rvsecncl_overseas
from kis_api.overseas_stock.inquire_nccs.inquire_nccs import inquire_nccs as inquire_nccs_overseas

def fetch_open_orders():
    """Step 1: Fetch open orders from both US and KR markets."""
    cano = ka.getTREnv().my_acct
    prod = ka.getTREnv().my_prod

    if MENU_DEBUG:
        logging.debug(f"[MenuDebug] Fetching Open Orders - Acct: {cano}")

    # Priority: Overseas -> Domestic
    market_found = "US"
    df = inquire_nccs_overseas(cano=cano, acnt_prdt_cd=prod, ovrs_excg_cd="NASD", sort_sqn="DS", FK200="", NK200="")

    if MENU_DEBUG and not df.empty:
        logging.debug(f"[MenuDebug] US Open Order Raw: {df.head(1).to_dict('records')}")

    if df.empty:
        market_found = "KR"
        df = inquire_psbl_rvsecncl(cano=cano, acnt_prdt_cd=prod, inqr_dvsn_1="0", inqr_dvsn_2="0")
        if MENU_DEBUG and not df.empty:
            logging.debug(f"[MenuDebug] KR Open Order Raw: {df.head(1).to_dict('records')}")

    return df, market_found

def print_open_orders_list(df, market):
    """Utility to format and return lines for the open orders list."""
    header_lines = ["="*40, " [Manage Open Orders]", "="*40]
    order_list = []

    def get_val(row_lower, keys, default=0):
        for k in keys:
            if k in row_lower: return row_lower[k]
        return default

    for idx, (_, row) in enumerate(df.iterrows()):
        name = row.get('prdt_name', row.get('pdno', 'Unknown'))
        row_lower = {k.lower(): v for k, v in row.items()}

        if market == "KR":
            side = "BUY " if row.get('sll_buy_dvsn_cd') == '02' else "SELL"
            price = int(float(row.get('ord_unpr', '0')))
            qty = row.get('psbl_qty', 0)
        else:
            side_name = get_val(row_lower, ['sll_buy_dvsn_cd_name', 'sll_buy_dvsn_name'], '?')
            side = side_name if side_name != '?' else ("BUY" if get_val(row_lower, ['sll_buy_dvsn_cd'], '')=='02' else "SELL")
            p_val = get_val(row_lower, ['ft_ord_unpr4', 'ft_ord_unpr3', 'ovrs_ord_unpr', 'ord_unpr'], '0')
            try: price = float(p_val)
            except: price = 0.0
            q_val = get_val(row_lower, ['nccs_qty', 'ft_ord_qty4', 'ord_qty'], 0)
            try: qty = int(float(q_val))
            except: qty = 0

        order_list.append(f" {idx+1}. [{market}] {name} | {side} | Prc: {price} | Qty: {qty}")
        if idx >= 6: break

    return header_lines + order_list

def execute_manage_action(market, action_type, order_data, new_price=None):
    """Step 5: Execute cancellation or correction."""
    cano = ka.getTREnv().my_acct
    prod = ka.getTREnv().my_prod
    t_ord = {k.lower(): v for k, v in order_data.items()}

    if MENU_DEBUG:
        logging.debug(f"[MenuDebug] Execute Manage - Mkt: {market}, Action: {action_type}, NewP: {new_price}, Target: {t_ord.get('pdno')} / {t_ord.get('odno')}")

    if market == "KR":
        ord_dvsn = t_ord.get('ord_dvsn_cd', t_ord.get('ord_dvsn', '00'))
        org_no = t_ord.get('ord_gno_brno', t_ord.get('krx_fwdg_ord_orgno', ''))
        excg_id = t_ord.get('excg_id_dvsn_cd', 'KRX')

        return order_rvsecncl(
            env_dv="real", cano=cano, acnt_prdt_cd=prod,
            krx_fwdg_ord_orgno=org_no, orgn_odno=t_ord.get('odno'),
            ord_dvsn=ord_dvsn,
            rvse_cncl_dvsn_cd="02" if action_type == '2' else "01",
            ord_qty=t_ord.get('psbl_qty'),
            ord_unpr=new_price if action_type == '1' else "0",
            qty_all_ord_yn="Y", excg_id_dvsn_cd=excg_id
        )
    else:
        # Overseas
        pdno = t_ord.get('pdno')
        orgn_odno = t_ord.get('odno')
        excg_cd = t_ord.get('ovrs_excg_cd', 'NASD')
        qty = t_ord.get('nccs_qty', t_ord.get('ft_ord_qty4', t_ord.get('ord_qty', 0)))

        return order_rvsecncl_overseas(
            cano=cano, acnt_prdt_cd=prod, ovrs_excg_cd=excg_cd, pdno=pdno,
            orgn_odno=orgn_odno,
            rvse_cncl_dvsn_cd="02" if action_type == '2' else "01",
            ord_qty=str(qty),
            ovrs_ord_unpr=new_price if action_type == '1' else "0",
            mgco_aptm_odno="", ord_svr_dvsn_cd="0", env_dv="real"
        )

def print_execution_result(df_res, err_msg=None):
    """Step 6: Print result of the management action."""
    header_lines = ["="*40, " [Order Result]", "="*40]

    is_success = False
    res_msg, res_odno = err_msg if err_msg else "Processed", ""

    if not df_res.empty:
        cols = {c.lower(): c for c in df_res.columns}
        if 'odno' in cols:
            is_success, res_odno = True, df_res.iloc[0][cols['odno']]
        elif 'ord_no' in cols:
            is_success, res_odno = True, df_res.iloc[0][cols['ord_no']]

        # If success, overwrite msg from df if available
        if is_success:
            if 'msg1' in cols: res_msg = df_res.iloc[0][cols['msg1']]
            elif 'message' in cols: res_msg = df_res.iloc[0][cols['message']]

    final_lines = header_lines + [
        f" Result : {'SUCCESS' if is_success else 'FAILED'}",
        f" Ord No : {res_odno}",
        f" Message: {res_msg}",
        " Press any key to return..."
    ]
    show_in_result_area(final_lines)
    msvcrt.getch()

def sync_open_orders():
    """Fetch open orders from API and sync them to display state."""
    add_alert("Syncing open orders...", "INFO")
    clear_order_states() # Clear locally tracked orders before fetching fresh ones
    df, market_found = fetch_open_orders()
    if not df.empty:
        for _, row in df.iterrows():
            row_lower = {k.lower(): v for k, v in row.items()}
            odno = row_lower.get('odno', row_lower.get('ord_no', 'Unknown'))
            pdno = row_lower.get('pdno', row_lower.get('stck_shrn_iscd', 'Unknown'))
            api_name = row_lower.get('prdt_name', row_lower.get('stck_nm', row_lower.get('stck_nm40', 'Unknown')))

            # Unify name source: Update Config if API returns a better/different name
            trading_config.update_stock_name(pdno, api_name)
            stock_info = trading_config.get_stock_info(pdno)
            display_name = stock_info.get('name', api_name)

            if market_found == "KR":
                side = "Buy" if row_lower.get('sll_buy_dvsn_cd') == '02' else "Sell"
                price = str(int(float(row_lower.get('ord_unpr', '0'))))
                qty = str(row_lower.get('psbl_qty', 0))
            else:
                # Use descriptive side text like "LOC Buy", fall back to Buy/Sell
                side_text = row_lower.get('sll_buy_dvsn_cd_name', row_lower.get('sll_buy_dvsn_name', '')).strip()
                if not side_text or side_text in ['?', 'nan', 'None', '']:
                    side = "Buy" if row_lower.get('sll_buy_dvsn_cd') == '02' else "Sell"
                else:
                    side = side_text

                p_val = row_lower.get('ft_ord_unpr3', row_lower.get('ft_ord_unpr4', row_lower.get('ovrs_ord_unpr', row_lower.get('ord_unpr', '0'))))
                price = f"${float(p_val):,.2f}" if float(p_val) > 0 else "Market"
                q_val = row_lower.get('nccs_qty', row_lower.get('ft_ord_qty4', row_lower.get('ord_qty', 0)))
                qty = str(int(float(q_val)))

            # Sync to bottom UI list without redundant alerts
            update_order_state(odno, pdno, display_name, side, price, qty, "PLACED", notify=False)
        add_alert(f"Sync complete ({len(df)} orders)", "SUCCESS")
    else:
        add_alert("Sync complete (No open orders)", "INFO")
    return not df.empty

def handle_manage_orders():
    """Main menu controller following the 6-step structure."""
    clear_result_area()
    try:
        # Step 1: Open order fetching
        show_in_result_area(["Fetching open orders..."])
        sync_open_orders()

        # We need the df for the management menu below, so fetch it again or adjust sync_open_orders
        # To keep it simple and correct, we'll just use the internal fetch here for the selection list
        df, market_found = fetch_open_orders()

        if df.empty:
            show_in_result_area(["No open orders found.", "Press any key to return..."])
            msvcrt.getch()
            return

        # Step 2: Determine which order to manage via user input
        display_lines = print_open_orders_list(df, market_found)
        show_in_result_area(display_lines)
        idx_s = input_at(len(display_lines)+2, 2, "Choice: ").strip()
        if idx_s.lower() == 'q' or not idx_s: return

        try:
            idx = int(idx_s) - 1
            if idx < 0 or idx >= len(df): raise ValueError
        except: return
        target_order = df.iloc[idx]

        # Step 3: Choose action (Correct or Cancel) via user input
        action = input_at(len(display_lines)+3, 2, "Action (1: Correct, 2: Cancel): ").strip()
        if action not in ['1', '2']: return

        # Step 4: Get new price for Correction via user input
        new_price = None
        if action == '1':
            new_price = input_at(len(display_lines)+4, 2, "New Price: ").strip()

        # Step 5: execute_manage_action
        df_res, err_msg = execute_manage_action(market_found, action, target_order, new_price)

        # Step 6: print result
        clear_result_area()
        # Clean terminal debris
        for r in range(10, 15): safe_write(f"\033[{r};1H{CLEAR_LINE}")
        print_execution_result(df_res, err_msg)

    except Exception as e:
        print_log(PrintLevel.ERROR, f"Order Manage Error: {e}")
    finally:
        render_ui(full_refresh=True)
