# -*- coding: utf-8 -*-
"""
KIS Wrapper Module

Simplified interface for common KIS API operations.
Reuses specialized managers for order and price management.
"""
import logging
import threading
import pandas as pd
from kis.kis_api import kis_auth as ka
from kis.order_manager import OrderManager
from core.display import update_order_state, add_alert, clear_order_states
from utils.format_utils import format_number
from core import trading_config

class PriceFetcher:
    """Handles REST-based price fetching with fallback logic."""
    @staticmethod
    def fetch_price(ticker: str, exchange: str = None) -> float:
        from kis.kis_api.overseas_stock.price import price as price_module
        if not exchange:
            exchange = trading_config.get_kis_exchange_code(ticker)
        try:
            env_dv = "demo" if ka.isPaperTrading() else "real"
            df = price_module.price("", exchange, ticker.upper(), env_dv)
            if df is not None and not df.empty:
                row = df.iloc[0]
                for field in ['last', 'base', 'ovrs_stck_prpr', 'stck_prpr', 'prpr', 'clpr']:
                    val = row.get(field)
                    if val and float(val) > 0:
                        return float(val)
            return 0.0
        except Exception as e:
            logging.warning(f"[PriceFetcher] {ticker} fetch failed: {e}")
            return 0.0

def fetch_open_orders():
    return OrderManager.fetch_open_orders()

def execute_manage_action(market, action_type, order_data, new_price=None):
    return OrderManager.execute_action(market, action_type, order_data, new_price)

def fetch_price(ticker: str, exchange: str = None) -> float:
    return PriceFetcher.fetch_price(ticker, exchange)

def sync_open_orders():
    """Sync open orders to the display state."""
    add_alert("[ORD] Syncing open orders...", "INFO")
    clear_order_states()
    try:
        df, num_us, num_kr = fetch_open_orders()
        add_alert(f"[ORD] updated! Orders US/KR : {num_us} / {num_kr}", "SUCCESS")
        if not df.empty:
            for _, row in df.iterrows():
                row_l = {k.lower(): v for k, v in row.items()}
                odno = row_l.get('odno', row_l.get('ord_no', 'Unknown'))
                pdno = row_l.get('pdno', row_l.get('stck_shrn_iscd', 'Unknown'))
                api_name = row_l.get('prdt_name', row_l.get('stck_nm', row_l.get('stck_nm40', 'Unknown')))

                trading_config.update_stock_name(pdno, api_name)
                stock_info = trading_config.get_stock_info(pdno)

                # Market-specific parsing
                market = row.get('_market', 'US')

                if market == "KR":
                    side = "Buy" if row_l.get('sll_buy_dvsn_cd') == '02' else "Sell"
                    price = str(int(float(row_l.get('ord_unpr', '0'))))
                    qty = str(row_l.get('psbl_qty', 0))
                else:
                    # US Market
                    side_text = row_l.get('sll_buy_dvsn_cd_name', row_l.get('sll_buy_dvsn_name', '')).strip()
                    if not side_text or side_text in ['?', 'nan', 'None', '']:
                        side = "Buy" if row_l.get('sll_buy_dvsn_cd') == '02' else "Sell"
                    else:
                        # Map Korean side text to English
                        if "매수" in side_text:
                            side = side_text.replace("매수", " Buy")
                        elif "매도" in side_text:
                            side = side_text.replace("매도", " Sell")
                        else:
                            side = side_text  # Fallback

                    # Price parsing (send raw number string, app.js handles formatting)
                    p_val = row_l.get('ft_ord_unpr3', row_l.get('ft_ord_unpr4', row_l.get('ovrs_ord_unpr', row_l.get('ord_unpr', '0'))))
                    try:
                        p_float = float(p_val)
                        if p_float > 0:
                            price = f"{p_float:.2f}"
                        else:
                            price = "Market"
                    except:
                        price = "0"

                    q_val = row_l.get('nccs_qty', row_l.get('ft_ord_qty4', row_l.get('ord_qty', 0)))
                    qty = str(int(float(q_val)))

                # Parse order time (ord_tmd: HHMMSS)
                raw_time = row_l.get('ord_tmd', '')
                time_str = None
                if raw_time and len(raw_time) == 6:
                    time_str = f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:]}"

                # Pass formatted strings to display (price first, then qty)
                update_order_state(odno, pdno, stock_info.get('name', api_name), side, price, qty, "PLACED", notify=False, time_str=time_str)
        return True
    except Exception as e:
        add_alert(f"Sync failed: {e}", "ERROR")
        return False
