"""
This module handles integrated account information inquiry for both KR and US markets.
It centralizes data fetching and provides an interactive terminal UI for portfolio monitoring.
"""
import msvcrt
import logging
import pandas as pd
import kis_api.kis_auth as ka
from display import clear_result_area, show_in_result_area, get_fixed_width_name
from kis_api.domestic_stock.inquire_balance.inquire_balance import inquire_balance
from kis_api.overseas_stock.inquire_present_balance.inquire_present_balance import inquire_present_balance
from .menu import MENU_DEBUG

def _get_val(d, keys, default=None):
    if hasattr(d, '_asdict'): d = d._asdict()
    if not isinstance(d, (dict, pd.Series)): return default
    for k in keys:
        if k in d:
            val = d[k]
            # Handle cases where value might be None or 'None' string
            if val is None or str(val).lower() == 'none': continue
            return val
    return default

def fetch_domestic_balance() -> dict:
    """Fetch Domestic Stock Balance and Assets (TTTC8434R)."""
    cano = ka.getTREnv().my_acct
    acnt_prdt_cd = ka.getTREnv().my_prod
    env_dv = "demo" if ka.isPaperTrading() else "real"
    if MENU_DEBUG:
        logging.debug(f"[MenuDebug] KR Environment: {env_dv}")

    result = {
        'stocks': [],
        'asset': {},
        'krw_orderable': 0,
        'error': None
    }

    df1, df2 = inquire_balance(
        env_dv=env_dv, cano=cano, acnt_prdt_cd=acnt_prdt_cd,
        afhr_flpr_yn="N", inqr_dvsn="02", unpr_dvsn="01",
        fund_sttl_icld_yn="N", fncg_amt_auto_rdpt_yn="N", prcs_dvsn="00"
    )

    if MENU_DEBUG and not df1.empty:
        logging.debug(f"[MenuDebug] KR DF1 Columns: {df1.columns.tolist()}")
        logging.debug(f"[MenuDebug] KR DF1 Row 0: {df1.iloc[0].to_dict()}")
    if MENU_DEBUG and not df2.empty:
        logging.debug(f"[MenuDebug] KR DF2 Row 0: {df2.iloc[0].to_dict()}")

    if not df1.empty:
        for item in df1.to_dict('records'):
            try:
                # Official API might return different casing or types; use _get_val
                mapped = {
                    'name': _get_val(item, ['prdt_name', 'PRDT_NAME'], 'Unknown'),
                    'qty': int(float(_get_val(item, ['hldg_qty', 'HLDG_QTY'], 0))),
                    'cur_price': float(_get_val(item, ['prpr', 'PRPR'], 0)),
                    'avg_price': float(_get_val(item, ['pchs_avg_pric', 'PCHS_AVG_PRIC', 'avg_unpr3'], 0)),
                    'pnl_rate': float(_get_val(item, ['evlu_pfls_rt', 'EVLU_PFLS_RT'], 0)),
                    'pnl_amt': float(_get_val(item, ['evlu_pfls_amt', 'EVLU_PFLS_AMT'], 0)),
                    'symbol': _get_val(item, ['pdno', 'PDNO'], '')
                }
                if mapped['qty'] > 0:
                    result['stocks'].append(mapped)
                    if MENU_DEBUG:
                        logging.debug(f"[MenuDebug] Mapped KR: {mapped['symbol']} {mapped['name']}")
            except Exception as e:
                logging.debug(f"Domestic stock mapping error: {e}")

    if not df2.empty:
        # Some API returns output2 as a single row DataFrame
        d_asset = df2.iloc[0].to_dict()
        result['asset'] = d_asset
        try: result['krw_orderable'] = int(float(_get_val(d_asset, ['prvs_rcdl_excc_amt', 'PRVS_RCDL_EXCC_AMT'], 0)))
        except: pass
    elif df1.empty:
        result['error'] = "No data returned from KR balance inquiry."

    return result

def fetch_overseas_balance() -> dict:
    """Fetch Overseas Stock Balance and Assets (CTRP6504R)."""
    cano = ka.getTREnv().my_acct
    acnt_prdt_cd = ka.getTREnv().my_prod
    env_dv = "demo" if ka.isPaperTrading() else "real"
    if MENU_DEBUG:
        logging.debug(f"[MenuDebug] US Environment: {env_dv}")


    result = {
        'stocks': [],
        'asset': {},
        'exchange_rate': 0.0,
        'error': None
    }

    df1, df2, df3 = inquire_present_balance(
        cano=cano, acnt_prdt_cd=acnt_prdt_cd,
        wcrc_frcr_dvsn_cd="02", natn_cd="000",
        tr_mket_cd="00", inqr_dvsn_cd="00", env_dv=env_dv
    )

    if MENU_DEBUG:
        if not df1.empty:
            logging.debug(f"[MenuDebug] US DF1 Columns: {df1.columns.tolist()}")
            logging.debug(f"[MenuDebug] US DF1 Row 0: {df1.iloc[0].to_dict()}")
        if not df2.empty:
            logging.debug(f"[MenuDebug] US DF2 Row 0: {df2.iloc[0].to_dict()}")
        if not df3.empty:
            logging.debug(f"[MenuDebug] US DF3 Row 0: {df3.iloc[0].to_dict()}")



    ex_rate = 0.0
    if not df1.empty:
        seen_ovs = set()
        for item in df1.to_dict('records'):
            try:
                if ex_rate == 0.0:
                    ex_rate = float(_get_val(item, ['bass_exrt', 'BASS_EXRT'], 0))

                symbol = _get_val(item, ['pdno', 'PDNO'], '') or _get_val(item, ['ovrs_pdno', 'OVRS_PDNO'], '')
                if not symbol or symbol in seen_ovs:
                    continue

                mapped = {
                    'name': _get_val(item, ['prdt_name', 'PRDT_NAME', 'ovrs_prdt_name'], 'Unknown'),
                    'qty': float(_get_val(item, ['ccld_qty_smtl1', 'CCLD_QTY_SMTL1', 'ovrs_cblc_qty', 'HLDG_QTY'], 0)),
                    'cur_price': float(_get_val(item, ['ovrs_now_pric1', 'OVRS_NOW_PRIC1', 'prpr'], 0)),
                    'avg_price': float(_get_val(item, ['avg_unpr3', 'pchs_avg_pric', 'PCHS_AVG_PRIC', 'avg_unpr1'], 0)),
                    'pnl_rate': float(_get_val(item, ['evlu_pfls_rt1', 'EVLU_PFLS_RT1', 'evlu_pfls_rt'], 0)),
                    'pnl_amt': float(_get_val(item, ['evlu_pfls_amt2', 'EVLU_PFLS_AMT2', 'evlu_pfls_amt'], 0)),
                    'symbol': symbol,
                    'exchange': _get_val(item, ['ovrs_excg_cd', 'OVRS_EXCG_CD'], 'US')
                }
                if mapped['qty'] > 0:
                    result['stocks'].append(mapped)
                    seen_ovs.add(symbol)
                    if MENU_DEBUG:
                        logging.debug(f"[MenuDebug] Mapped US: {mapped['symbol']} {mapped['name']}")
                else:
                    if MENU_DEBUG:
                        logging.debug(f"[MenuDebug] Skipping US (0 qty): {symbol}")
                    continue
            except Exception as e:
                logging.debug(f"Overseas stock mapping error: {e}")

    asset = {}
    if not df2.empty:
        o2 = df2.iloc[0].to_dict()
        asset.update(o2)
        if ex_rate == 0.0:
            ex_rate = float(_get_val(o2, ['frst_bltn_exrt', 'FRST_BLTN_EXRT'], 0))
    if not df3.empty:
        o3 = df3.iloc[0].to_dict()
        asset.update(o3)

    result['asset'] = asset
    result['exchange_rate'] = ex_rate
    if df1.empty and df2.empty:
        result['error'] = "No data returned from US balance inquiry."

    return result

def fetch_account_data():
    """Fetch all necessary data for account info."""
    kr = fetch_domestic_balance()
    us = fetch_overseas_balance()

    # Map to the format expected by print_account_info
    return {
        'domestic_stocks': kr['stocks'],
        'overseas_stocks': us['stocks'],
        'domestic_asset': kr['asset'],
        'overseas_asset': us['asset'],
        'exchange_rate': us['exchange_rate'],
        'krw_orderable': kr['krw_orderable'],
        'error': f"{kr['error']} | {us['error']}" if (kr['error'] or us['error']) else None
    }

def print_account_info(data):
    """Render the account information UI and handle user navigation."""
    # State
    view_mode = 0 # 0: Summary, 1: US List, 2: KR List
    page_idx = 0
    ROWS_PER_PAGE = 5

    # Pre-calc Summary Data
    ex_rate = data.get('exchange_rate', 0.0)

    # --- KR Summary ---
    d_orderable = data.get('krw_orderable', 0)

    d_pl_amt = 0.0
    d_pchs_amt = 0.0
    for stock in data['domestic_stocks']:
        d_pl_amt += stock['pnl_amt']
        d_pchs_amt += (stock['avg_price'] * stock['qty'])

    d_stock_eval = d_pchs_amt + d_pl_amt
    d_tot_assets = d_stock_eval + d_orderable
    d_pl_rate = (d_pl_amt / d_pchs_amt * 100) if d_pchs_amt > 0 else 0.0

    # --- US Summary ---
    o_asset = data['overseas_asset']
    o_orderable_usd = float(o_asset.get('frcr_drwg_psbl_amt_1', 0))

    o_pl_amt_usd = 0.0
    o_pchs_amt_usd = 0.0
    o_stock_eval_usd = 0.0

    for stock in data['overseas_stocks']:
        o_pl_amt_usd += stock['pnl_amt']
        pchs = stock['avg_price'] * stock['qty']
        o_pchs_amt_usd += pchs
        o_stock_eval_usd += (stock['cur_price'] * stock['qty'])

    o_pl_rate = (o_pl_amt_usd / o_pchs_amt_usd * 100) if o_pchs_amt_usd > 0 else 0.0
    o_tot_assets_usd = o_stock_eval_usd + o_orderable_usd

    while True:
        clear_result_area()
        lines = []
        SEPARATOR_LEN = 95

        # --- VIEW 0: SUMMARY ---
        if view_mode == 0:
            lines.append("=" * SEPARATOR_LEN)
            lines.append(f" [Account Summary] exchange rate : {ex_rate:,.2f} KRW/USD")
            lines.append("=" * SEPARATOR_LEN)
            lines.append(f" [KR] Total assets: {d_tot_assets:,.0f} KRW | Orderable: {d_orderable:,.0f} KRW")
            lines.append(f"      PL Amt      : {d_pl_amt:,.0f} KRW ({d_pl_rate:+.2f} %)")
            lines.append("-" * SEPARATOR_LEN)
            lines.append(f" [US] Total assets: ${o_tot_assets_usd:,.2f} | Orderable: ${o_orderable_usd:,.2f}")
            lines.append(f"      PL Amt      : ${o_pl_amt_usd:,.2f} ({o_pl_rate:+.2f} %)")
            lines.append("=" * SEPARATOR_LEN)
            lines.append(f" [f] Toggle View(US List)  [q] Quit")

        # --- VIEW 1 & 2: LIST ---
        else:
            is_us = (view_mode == 1)
            target_list = data['overseas_stocks'] if is_us else data['domestic_stocks']
            title = "US Stocks" if is_us else "KR Stocks"

            l_pl_amt = o_pl_amt_usd if is_us else d_pl_amt
            l_pl_rate = o_pl_rate if is_us else d_pl_rate
            l_stock_eval = o_stock_eval_usd if is_us else d_stock_eval

            total_items = len(target_list)
            total_pages = (total_items + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
            if total_pages == 0: total_pages = 1
            if page_idx >= total_pages: page_idx = 0

            lines.append(f" [Portfolio: {title}] ({page_idx+1}/{total_pages})")

            # Header
            header_fmt = " {:<6} | {} | {:>6} | {:>9} | {:>9} | {:>9} | {:>7}"
            hdr_name = get_fixed_width_name("Name", 20)
            lines.append(header_fmt.format("Ticker", hdr_name, "Qty", "Avg", "Cur", "P/L", "P/L%"))
            lines.append("=" * SEPARATOR_LEN)

            start_idx = page_idx * ROWS_PER_PAGE
            end_idx = start_idx + ROWS_PER_PAGE
            page_items = target_list[start_idx:end_idx]

            if not page_items:
                lines.append("  (No holdings)")
                for _ in range(ROWS_PER_PAGE-1): lines.append("")
            else:
                for item in page_items:
                    ticker = str(item.get('symbol', ''))[:6]
                    name = get_fixed_width_name(item['name'], 20)
                    if is_us:
                        q_val = item['qty']
                        qty = f"{int(q_val):,}" if q_val.is_integer() else f"{q_val:,.2f}"
                        avg = f"${item['avg_price']:,.2f}"
                        cur = f"${item['cur_price']:,.2f}"
                        pl_val = f"${item['pnl_amt']:,.2f}"
                    else:
                        qty = f"{item['qty']:,}"
                        avg = f"{item['avg_price']:,.0f}"
                        cur = f"{item['cur_price']:,.0f}"
                        pl_val = f"{item['pnl_amt']:,.0f}"

                    pnl_pct = f"{item['pnl_rate']:.2f}%"
                    lines.append(header_fmt.format(ticker, name, qty, avg, cur, pl_val, pnl_pct))

                rem = ROWS_PER_PAGE - len(page_items)
                for _ in range(rem): lines.append("")

            lines.append("-" * SEPARATOR_LEN)
            rate_str = f"{l_pl_rate:+.2f}%"
            if l_pl_amt < 0 and "0.00%" in rate_str and "+" in rate_str:
                rate_str = rate_str.replace("+", "-")

            if is_us:
                tot_str = f" Total: ${l_stock_eval:,.2f}       P/L: ${l_pl_amt:,.2f} ({rate_str})"
            else:
                tot_str = f" Total: {l_stock_eval:,.0f} KRW       P/L: {l_pl_amt:,.0f} KRW ({rate_str})"
            lines.append(tot_str)

            next_view = "KR List" if is_us else "Summary"
            lines.append(f" [n] Next Page  [f] Toggle({next_view})  [q] Quit")

        show_in_result_area(lines)

        ch = msvcrt.getch()
        if ch == b'q':
            clear_result_area()
            break
        elif ch == b'f':
            view_mode = (view_mode + 1) % 3
            page_idx = 0
        elif ch == b'n':
            if view_mode != 0:
                page_idx += 1
                if page_idx >= total_pages: page_idx = 0

def handle_account_info():
    """Main menu controller for account information."""
    clear_result_area()
    show_in_result_area(["Fetching integrated account data..."])
    data = fetch_account_data()
    print_account_info(data)
