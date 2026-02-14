# -*- coding: utf-8 -*-
"""
KIS WebSocket Manager Module

Handles WebSocket connection, subscriptions, and event loop.
"""
import logging
import threading
from typing import Optional, List
from kis.kis_api import kis_auth as ka
from thread_state import update_kis_state, WebSocketStatus
import trading_config
from display import add_alert

class WSManager:
    """Manages KIS WebSocket life cycle and subscriptions."""

    def __init__(self):
        self._ws_instance: Optional[ka.KISWebSocket] = None
        self._ws_thread: Optional[threading.Thread] = None

    def initialize(self) -> bool:
        """Initialize WebSocket subscriptions and start the connection thread."""
        try:
            # Import specific subscription handlers
            from kis.kis_api.domestic_stock.asking_price_total.asking_price_total import asking_price_total
            from kis.kis_api.domestic_stock.ccnl_total.ccnl_total import ccnl_total
            from kis.kis_api.domestic_stock.ccnl_notice.ccnl_notice import ccnl_notice as ccnl_notice_kr
            from kis.kis_api.overseas_stock.asking_price.asking_price import asking_price
            from kis.kis_api.overseas_stock.ccnl_notice.ccnl_notice import ccnl_notice as ccnl_notice_us
            from kis.kis_api.overseas_stock.delayed_ccnl.delayed_ccnl import delayed_ccnl
            from kis.event_handler import on_result

            logging.info("[WSManager] Initializing WebSocket...")
            self._ws_instance = ka.KISWebSocket(api_url="")

            # 1. Personal Order Notifications
            htsid = ka.getTREnv().my_htsid
            if htsid:
                self._ws_instance.subscribe(ccnl_notice_kr, htsid, kwargs={"env_dv": "real"})
                self._ws_instance.subscribe(ccnl_notice_us, htsid, kwargs={"env_dv": "real"})

            # 2. Market Data Subscriptions (KR)
            watch_list_kr = [s["ticker"] for s in trading_config.CONFIG.get("KR", []) if not s.get("disabled")]
            if watch_list_kr:
                self._ws_instance.subscribe(asking_price_total, watch_list_kr)
                self._ws_instance.subscribe(ccnl_total, watch_list_kr)

            # 3. Market Data Subscriptions (US)
            watch_list_us = [s["ticker"] for s in trading_config.CONFIG.get("US", []) if not s.get("disabled")]
            if watch_list_us:
                formatted_us = [trading_config.get_kis_market_prefix(t) for t in watch_list_us]
                self._ws_instance.subscribe(asking_price, formatted_us)
                self._ws_instance.subscribe(delayed_ccnl, formatted_us)

            # 4. Set Callback & Start
            self._set_callback(on_result)
            self._ws_thread = threading.Thread(
                target=self._ws_instance.start, 
                args=(on_result,), 
                daemon=True,
                name="WSThread"
            )
            self._ws_thread.start()

            update_kis_state(ws_status=WebSocketStatus.CONNECTING)
            logging.info("[WSManager] WebSocket thread started")
            add_alert("[KIS] WebSocket connecting...", "INFO")
            return True

        except Exception as e:
            logging.error(f"[WSManager] Init failed: {e}")
            update_kis_state(ws_status=WebSocketStatus.ERROR, last_error=str(e))
            return False

    def _set_callback(self, callback):
        if hasattr(self._ws_instance, 'add_callback'):
            self._ws_instance.add_callback(callback)
        elif hasattr(self._ws_instance, 'on'):
            self._ws_instance.on("message", callback)
        else:
            self._ws_instance.callback = callback
            
    def is_alive(self) -> bool:
        return self._ws_thread is not None and self._ws_thread.is_alive()
