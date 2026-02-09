"""
This module handles the management of open orders (cancellation and correction).
Extracted from menu/handle_manage_orders.py
"""
import logging
import threading
import pandas as pd
from kis.kis_api import kis_auth as ka
import trading_config
from display import update_order_state, add_alert, clear_order_states
from kis.kis_api.domestic_stock.order_rvsecncl.order_rvsecncl import order_rvsecncl
from kis.kis_api.domestic_stock.inquire_psbl_rvsecncl.inquire_psbl_rvsecncl import inquire_psbl_rvsecncl
from kis.kis_api.overseas_stock.order_rvsecncl.order_rvsecncl import order_rvsecncl as order_rvsecncl_overseas
from kis.kis_api.overseas_stock.inquire_nccs.inquire_nccs import inquire_nccs as inquire_nccs_overseas
from kis.kis_api.overseas_stock.price import price as price_module

# Centralized debug toggle (using global logging level instead)
MENU_DEBUG = False

class SyncManager:
    """Manages order synchronization to prevent race conditions and redundant API calls."""
    _sync_timer = None
    _sync_lock = threading.Lock()
    _last_request_time = 0
    _debounce_seconds = 1.0

    @classmethod
    def request_sync(cls):
        """Request a sync with debouncing. Resets the 1s timer on each call."""
        with cls._sync_lock:
            if cls._sync_timer:
                cls._sync_timer.cancel()

            cls._sync_timer = threading.Timer(cls._debounce_seconds, cls._execute_sync)
            cls._sync_timer.daemon = True
            cls._sync_timer.start()

    @classmethod
    def _execute_sync(cls):
        """The actual sync execution. Wrapped in a lock to prevent concurrent runs."""
        # Use a high-level lock to ensure only one sync runs at a time
        if not cls._sync_lock.acquire(blocking=False):
            # If already running, we might need another sync after this one finishes
            # but for now, we just return to avoid overlapping.
            return

        try:
            sync_open_orders()
        finally:
            cls._sync_lock.release()

def request_sync():
    """Public helper to request a debounced sync."""
    SyncManager.request_sync()

def fetch_open_orders():
    """Step 1: Fetch open orders from both US and KR markets and return a combined DataFrame."""
    cano = ka.getTREnv().my_acct
    prod = ka.getTREnv().my_prod

    # 1. US Markets (NASD, NYSE, AMEX)
    us_exchanges = ["NASD", "NYSE", "AMEX"]
    df_us_list = []
    for excg_cd in us_exchanges:
        df = inquire_nccs_overseas(cano=cano, acnt_prdt_cd=prod, ovrs_excg_cd=excg_cd, sort_sqn="DS", FK200="", NK200="")
        if not df.empty:
            df['_market'] = 'US'
            df_us_list.append(df)

    df_us = pd.concat(df_us_list, ignore_index=True) if df_us_list else pd.DataFrame()

    # 2. KR Market
    df_kr = inquire_psbl_rvsecncl(cano=cano, acnt_prdt_cd=prod, inqr_dvsn_1="0", inqr_dvsn_2="0")
    if not df_kr.empty:
        df_kr['_market'] = 'KR'

    # Combine
    if df_us.empty and df_kr.empty:
        return pd.DataFrame(), 0, 0

    combined_df = pd.concat([df_us, df_kr], ignore_index=True)
    return combined_df, len(df_us), len(df_kr)

def execute_manage_action(market, action_type, order_data, new_price=None):
    """Step 5: Execute cancellation or correction."""
    cano = ka.getTREnv().my_acct
    prod = ka.getTREnv().my_prod
    t_ord = {k.lower(): v for k, v in order_data.items()}

    if MENU_DEBUG:
        logging.debug(f"[Manager] Execute Manage - Mkt: {market}, Action: {action_type}, NewP: {new_price}, Target: {t_ord.get('pdno')} / {t_ord.get('odno')}")

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

def sync_open_orders():
    """Fetch open orders from API and sync them to display state."""
    add_alert("[ORD] Syncing open orders...", "INFO")
    clear_order_states() # Clear locally tracked orders before fetching fresh ones
    try:
        df, num_us, num_kr = fetch_open_orders()
    except Exception as e:
        add_alert(f"Sync failed: {e}", "ERROR")
        return False

    # Priority Alert Message requested by user
    alert_msg = f"[ORD] updated! Orders US/KR : {num_us} / {num_kr}"
    add_alert(alert_msg, "SUCCESS")

    if not df.empty:
        for _, row in df.iterrows():
            market = row.get('_market', 'US')
            row_lower = {k.lower(): v for k, v in row.items()}
            odno = row_lower.get('odno', row_lower.get('ord_no', 'Unknown'))
            pdno = row_lower.get('pdno', row_lower.get('stck_shrn_iscd', 'Unknown'))
            api_name = row_lower.get('prdt_name', row_lower.get('stck_nm', row_lower.get('stck_nm40', 'Unknown')))

            trading_config.update_stock_name(pdno, api_name)
            stock_info = trading_config.get_stock_info(pdno)
            display_name = stock_info.get('name', api_name)

            if market == "KR":
                side = "Buy" if row_lower.get('sll_buy_dvsn_cd') == '02' else "Sell"
                price = str(int(float(row_lower.get('ord_unpr', '0'))))
                qty = str(row_lower.get('psbl_qty', 0))
            else:
                side_text = row_lower.get('sll_buy_dvsn_cd_name', row_lower.get('sll_buy_dvsn_name', '')).strip()
                if not side_text or side_text in ['?', 'nan', 'None', '']:
                    side = "Buy" if row_lower.get('sll_buy_dvsn_cd') == '02' else "Sell"
                else:
                    side = side_text

                p_val = row_lower.get('ft_ord_unpr3', row_lower.get('ft_ord_unpr4', row_lower.get('ovrs_ord_unpr', row_lower.get('ord_unpr', '0'))))
                price = f"${float(p_val):,.2f}" if float(p_val) > 0 else "Market"
                q_val = row_lower.get('nccs_qty', row_lower.get('ft_ord_qty4', row_lower.get('ord_qty', 0)))
                qty = str(int(float(q_val)))

            # Sync to bottom UI list
            update_order_state(odno, pdno, display_name, side, price, qty, "PLACED", notify=False)
    return not df.empty

def fetch_price(ticker: str, exchange: str = None) -> float:
    """
    Fetch current price for an overseas stock from KIS API.

    Args:
        ticker: Stock ticker symbol (e.g., 'QLD', 'SOXL')
        exchange: Exchange code (NAS, NYS, AMS). If None, auto-mapping via config.

    Returns:
        Current price as float, or 0.0 if failed
    """
    if not exchange:
        exchange = trading_config.get_kis_exchange_code(ticker)

    try:
        env_dv = "demo" if ka.isPaperTrading() else "real"
        df = price_module.price("", exchange, ticker.upper(), env_dv)

        if df is not None and not df.empty:
            row = df.iloc[0]

            # Try multiple possible field names for current price
            # 'last' is real-time price, 'base' is previous close (used when market is closed)
            price_fields = ['last', 'base', 'ovrs_stck_prpr', 'stck_prpr', 'prpr', 'clpr']
            for field in price_fields:
                if field in row:
                    val = row[field]
                    # Skip if value is None, empty string, or falsy (but not '0')
                    if val is None or val == '':
                        continue
                    try:
                        price_val = float(val)
                        if price_val > 0:
                            logging.info(f"[KIS API] {ticker} price fetched: {price_val} (field: {field})")
                            return price_val
                    except (ValueError, TypeError):
                        continue

            # No price found
            logging.warning(f"[KIS API] {ticker}: No valid price available in response")

        return 0.0

    except Exception as e:
        logging.warning(f"Failed to fetch price from KIS API for {ticker}: {e}")
        return 0.0
