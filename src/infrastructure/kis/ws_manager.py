# -*- coding: utf-8 -*-
"""KIS WebSocket connection, subscription, and event-loop manager."""
import logging
import threading
from typing import Callable, Optional, cast

from infrastructure.kis.kis_api import kis_auth as ka

_domestic_enabled: Optional[Callable[[], bool]] = None
_domestic_tickers: Optional[Callable[[], list[str]]] = None
_overseas_tickers: Optional[Callable[[], list[str]]] = None
_market_prefix: Optional[Callable[[str], str]] = None
_alert_publisher: Optional[Callable[[str, str], None]] = None
_state_publisher: Optional[Callable[[str, Optional[str]], None]] = None
_event_handler: Optional[Callable[..., None]] = None


def configure_subscription_provider(
    *,
    domestic_enabled: Optional[Callable[[], bool]],
    domestic_tickers: Optional[Callable[[], list[str]]],
    overseas_tickers: Optional[Callable[[], list[str]]],
    market_prefix: Optional[Callable[[str], str]],
) -> None:
    """Inject KIS subscription configuration at composition time."""
    global _domestic_enabled, _domestic_tickers, _overseas_tickers, _market_prefix
    _domestic_enabled = domestic_enabled
    _domestic_tickers = domestic_tickers
    _overseas_tickers = overseas_tickers
    _market_prefix = market_prefix


def configure_alert_publisher(publisher: Optional[Callable[[str, str], None]]) -> None:
    """Inject best-effort WebSocket alert delivery."""
    global _alert_publisher
    _alert_publisher = publisher


def configure_state_publisher(
    publisher: Optional[Callable[[str, Optional[str]], None]],
) -> None:
    """Inject WebSocket lifecycle state delivery."""
    global _state_publisher
    _state_publisher = publisher


def configure_event_handler(handler: Optional[Callable[..., None]]) -> None:
    """Inject the application-owned KIS event handler."""
    global _event_handler
    _event_handler = handler


def _publish_alert(message: str, level: str) -> None:
    if _alert_publisher is None:
        return
    try:
        _alert_publisher(message, level)
    except Exception as error:
        logging.warning("[WSManager] Alert publication failed: %s", error)


def _publish_state(status: str, error: Optional[str] = None) -> None:
    if _state_publisher is None:
        return
    try:
        _state_publisher(status, error)
    except Exception as publish_error:
        logging.warning("[WSManager] State publication failed: %s", publish_error)


def _runtime_collaborators() -> tuple[
    Callable[[], bool],
    Callable[[], list[str]],
    Callable[[], list[str]],
    Callable[[str], str],
    Callable[..., None],
]:
    if None in (
        _domestic_enabled,
        _domestic_tickers,
        _overseas_tickers,
        _market_prefix,
        _event_handler,
    ):
        raise RuntimeError("KIS WebSocket runtime collaborators are not configured")
    return (
        cast(Callable[[], bool], _domestic_enabled),
        cast(Callable[[], list[str]], _domestic_tickers),
        cast(Callable[[], list[str]], _overseas_tickers),
        cast(Callable[[str], str], _market_prefix),
        cast(Callable[..., None], _event_handler),
    )


class WSManager:
    """Manages KIS WebSocket life cycle and subscriptions."""

    def __init__(self):
        self._ws_instance: Optional[ka.KISWebSocket] = None
        self._ws_thread: Optional[threading.Thread] = None

    def initialize(self) -> bool:
        """Initialize WebSocket subscriptions and start the connection thread."""
        try:
            if self.is_alive():
                logging.info("[WSManager] WebSocket already running")
                return True

            (
                domestic_enabled,
                domestic_tickers,
                overseas_tickers,
                market_prefix,
                event_handler,
            ) = _runtime_collaborators()

            if hasattr(ka, "open_map"):
                ka.open_map.clear()

            from infrastructure.kis.kis_api.overseas_stock.asking_price.asking_price import (
                asking_price,
            )
            from infrastructure.kis.kis_api.overseas_stock.ccnl_notice.ccnl_notice import (
                ccnl_notice as ccnl_notice_us,
            )
            from infrastructure.kis.kis_api.overseas_stock.delayed_ccnl.delayed_ccnl import (
                delayed_ccnl,
            )

            logging.info("[WSManager] Initializing WebSocket...")
            self._ws_instance = ka.KISWebSocket(api_url="")
            is_domestic_enabled = domestic_enabled()

            # 1. Personal Order Notifications
            htsid = ka.getTREnv().my_htsid
            if htsid:
                self._ws_instance.subscribe(ccnl_notice_us, htsid, kwargs={"env_dv": "real"})
                if is_domestic_enabled:
                    from infrastructure.kis.kis_api.domestic_stock.ccnl_notice.ccnl_notice import (
                        ccnl_notice as ccnl_notice_kr,
                    )

                    self._ws_instance.subscribe(
                        ccnl_notice_kr,
                        htsid,
                        kwargs={"env_dv": "real"},
                    )

            # 2. Market Data Subscriptions (KR)
            if is_domestic_enabled:
                from infrastructure.kis.kis_api.domestic_stock.asking_price_total.asking_price_total import (
                    asking_price_total,
                )
                from infrastructure.kis.kis_api.domestic_stock.ccnl_total.ccnl_total import (
                    ccnl_total,
                )

                watch_list_kr = domestic_tickers()
                if watch_list_kr:
                    self._ws_instance.subscribe(asking_price_total, watch_list_kr)
                    self._ws_instance.subscribe(ccnl_total, watch_list_kr)

            # 3. Market Data Subscriptions (US)
            watch_list_us = overseas_tickers()
            if watch_list_us:
                formatted_us = [market_prefix(ticker) for ticker in watch_list_us]
                self._ws_instance.subscribe(asking_price, formatted_us)
                self._ws_instance.subscribe(delayed_ccnl, formatted_us)

            # 4. Set Callback & Start
            self._set_callback(event_handler)
            self._ws_thread = threading.Thread(
                target=self._ws_instance.start,
                args=(event_handler,),
                daemon=True,
                name="WSThread"
            )
            self._ws_thread.start()

            _publish_state("connecting")
            logging.info("[WSManager] WebSocket thread started")
            _publish_alert("[KIS] WebSocket connecting...", "INFO")
            return True

        except Exception as e:
            logging.error(f"[WSManager] Init failed: {e}")
            _publish_state("error", str(e))
            return False

    def _set_callback(self, callback):
        ws_instance = cast(ka.KISWebSocket, self._ws_instance)
        if hasattr(ws_instance, 'add_callback'):
            ws_instance.add_callback(callback)
        elif hasattr(ws_instance, 'on'):
            ws_instance.on("message", callback)
        else:
            ws_instance.callback = callback

    def is_alive(self) -> bool:
        return self._ws_thread is not None and self._ws_thread.is_alive()

    def stop(self):
        """Request WebSocket shutdown and wait briefly for the thread."""
        if self._ws_instance and hasattr(self._ws_instance, "stop"):
            self._ws_instance.stop()
        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=5.0)
            if self._ws_thread.is_alive():
                logging.warning("[WSManager] WebSocket thread did not stop within timeout")
                _publish_alert("[KIS] WebSocket stop requested; thread still running", "WARNING")
                return

        self._ws_instance = None
        self._ws_thread = None
        _publish_state("disconnected")
        _publish_alert("[KIS] WebSocket stopped", "INFO")
