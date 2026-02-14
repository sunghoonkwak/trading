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
from display import update_order_state, add_alert, clear_order_states
import trading_config

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
                
                side = "Buy" if row_l.get('sll_buy_dvsn_cd') == '02' else "Sell"
                # (US Market specialized side text logic can be added here)
                
                update_order_state(odno, pdno, stock_info.get('name', api_name), side, "0", "0", "PLACED", notify=False)
        return True
    except Exception as e:
        add_alert(f"Sync failed: {e}", "ERROR")
        return False

def request_sync():
    """Helper for debounced sync."""
    # Reusing existing debouncing logic if needed, but for simplicity:
    sync_open_orders()
