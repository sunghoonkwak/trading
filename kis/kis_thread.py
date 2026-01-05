# -*- coding: utf-8 -*-
"""
KIS Thread Module

This module implements the dedicated KIS API thread that handles:
- Authentication (REST API and WebSocket)
- API calls requested from Main thread
- WebSocket connection management
- Google Sheets access
- Event pipe management for viewer
"""
import logging
import threading
import time
from queue import Empty
from typing import Optional, Callable
from datetime import datetime

from kis.kis_api import kis_auth as ka

from thread_comm import (
    kis_request_queue, kis_response_queue, kis_status_queue, data_queue,
    ThreadRequest, ThreadResponse, RequestType
)
from thread_state import (
    ThreadStatus, AuthStatus, WebSocketStatus,
    update_kis_state, get_kis_state
)


# Module-level references
_kis_thread: Optional[threading.Thread] = None
_ws_instance = None
_stop_event = threading.Event()


def _handle_request(request: ThreadRequest) -> ThreadResponse:
    """
    Process a single request from the queue.

    Args:
        request: The ThreadRequest to process

    Returns:
        ThreadResponse with result or error
    """
    try:
        if request.request_type == RequestType.KIS_AUTH:
            return _handle_auth(request)

        elif request.request_type == RequestType.KIS_WS_AUTH:
            return _handle_ws_auth(request)

        elif request.request_type == RequestType.GET_PORTFOLIO:
            return _handle_get_portfolio(request)

        else:
            return ThreadResponse(
                request_id=request.request_id,
                success=False,
                error=f"Unknown request type: {request.request_type}"
            )

    except Exception as e:
        logging.error(f"[KIS Thread] Error handling request {request.request_id}: {e}")
        return ThreadResponse(
            request_id=request.request_id,
            success=False,
            error=str(e)
        )


def _handle_auth(request: ThreadRequest) -> ThreadResponse:
    """Handle REST API authentication."""
    update_kis_state(auth_status=AuthStatus.AUTHENTICATING)

    try:
        ka.auth()
        update_kis_state(auth_status=AuthStatus.AUTHENTICATED)
        logging.info("[KIS Thread] REST API authentication successful")

        return ThreadResponse(
            request_id=request.request_id,
            success=True,
            result={"status": "authenticated"}
        )

    except Exception as e:
        update_kis_state(auth_status=AuthStatus.FAILED, last_error=str(e))
        logging.error(f"[KIS Thread] REST API authentication failed: {e}")

        return ThreadResponse(
            request_id=request.request_id,
            success=False,
            error=str(e)
        )


def _handle_ws_auth(request: ThreadRequest) -> ThreadResponse:
    """Handle WebSocket authentication."""
    update_kis_state(ws_auth_status=AuthStatus.AUTHENTICATING)

    try:
        ka.auth_ws()
        update_kis_state(ws_auth_status=AuthStatus.AUTHENTICATED)
        logging.info("[KIS Thread] WebSocket authentication successful")

        return ThreadResponse(
            request_id=request.request_id,
            success=True,
            result={"status": "ws_authenticated"}
        )

    except Exception as e:
        update_kis_state(ws_auth_status=AuthStatus.FAILED, last_error=str(e))
        logging.error(f"[KIS Thread] WebSocket authentication failed: {e}")

        return ThreadResponse(
            request_id=request.request_id,
            success=False,
            error=str(e)
        )


# =============================================================================
# WebSocket and Event Pipe Management
# =============================================================================

_ws_thread: Optional[threading.Thread] = None
_pipe_thread: Optional[threading.Thread] = None


def initialize_websocket_and_pipe() -> bool:
    """
    Initialize WebSocket subscriptions and event_pipe server.

    This should be called after both REST and WS auth are complete.
    Returns True if successful.
    """
    global _ws_instance, _ws_thread, _pipe_thread

    try:
        import trading_config
        from kis import event_pipe
        from display import render_ui, add_alert

        # Import WebSocket subscription functions
        from kis.kis_api.domestic_stock.asking_price_total.asking_price_total import asking_price_total
        from kis.kis_api.domestic_stock.ccnl_total.ccnl_total import ccnl_total
        from kis.kis_api.domestic_stock.ccnl_notice.ccnl_notice import ccnl_notice as ccnl_notice_kr
        from kis.kis_api.overseas_stock.asking_price.asking_price import asking_price
        from kis.kis_api.overseas_stock.ccnl_notice.ccnl_notice import ccnl_notice as ccnl_notice_us
        from kis.kis_api.overseas_stock.delayed_ccnl.delayed_ccnl import delayed_ccnl

        # Import on_result callback from main
        from kis.event_handler import on_result

        logging.info("[KIS Thread] Initializing WebSocket...")

        # Create WebSocket instance
        _ws_instance = ka.KISWebSocket(api_url="")

        # Load stocks to watch
        watch_list_kr = [s["ticker"] for s in trading_config.CONFIG.get("KR", []) if not s.get("disabled", False)]
        watch_list_us = [s["ticker"] for s in trading_config.CONFIG.get("US", []) if not s.get("disabled", False)]

        # Personal Notifications (Order notifications)
        htsid = ka.getTREnv().my_htsid
        if htsid:
            # Domestic (Korean) stock order notifications
            _ws_instance.subscribe(ccnl_notice_kr, htsid, kwargs={"env_dv": "real"})
            # Overseas (US) stock order notifications
            _ws_instance.subscribe(ccnl_notice_us, htsid, kwargs={"env_dv": "real"})

        if watch_list_kr:
            _ws_instance.subscribe(asking_price_total, watch_list_kr)
            _ws_instance.subscribe(ccnl_total, watch_list_kr)

        if watch_list_us:
            from trading_config import get_kis_market_prefix
            formatted_us_list = [get_kis_market_prefix(ticker) for ticker in watch_list_us]
            _ws_instance.subscribe(asking_price, formatted_us_list)
            _ws_instance.subscribe(delayed_ccnl, formatted_us_list)

        # Set callback
        if hasattr(_ws_instance, 'add_callback'):
            _ws_instance.add_callback(on_result)
        elif hasattr(_ws_instance, 'on'):
            _ws_instance.on("message", on_result)
        else:
            _ws_instance.callback = on_result

        # Start WebSocket in background thread
        _ws_thread = threading.Thread(target=_ws_instance.start, args=(on_result,), daemon=True)
        _ws_thread.start()

        update_kis_state(ws_status=WebSocketStatus.CONNECTING)
        logging.info("[KIS Thread] WebSocket started")
        add_alert("[KIS] WebSocket connecting...", "INFO")

        # Pipe server is already created and managed by main.py
        # Event pipe callback registration removed as render_ui is No-op
        logging.info("[KIS Thread] Event pipe linked (No-op UI callback skipped)")
        add_alert("[KIS] Event pipe linked", "SUCCESS")

        return True

    except Exception as e:
        logging.error(f"[KIS Thread] WebSocket/Pipe init failed: {e}")
        update_kis_state(ws_status=WebSocketStatus.ERROR, last_error=str(e))
        return False


def _handle_get_portfolio(request: ThreadRequest) -> ThreadResponse:
    """Handle get_portfolio request."""
    try:
        from kis.get_portfolio import get_portfolio

        result = get_portfolio()

        return ThreadResponse(
            request_id=request.request_id,
            success=True if result.get("error") is None else False,
            result=result,
            error=result.get("error")
        )

    except Exception as e:
        logging.error(f"[KIS Thread] get_portfolio failed: {e}")
        return ThreadResponse(
            request_id=request.request_id,
            success=False,
            error=str(e)
        )


def _handle_api_call(request: ThreadRequest) -> ThreadResponse:
    """Handle generic KIS API call."""
    func_name = request.func_name
    args = request.args
    kwargs = request.kwargs

    try:
        # Dynamically get the function from kis_api module
        if hasattr(ka, func_name):
            func = getattr(ka, func_name)
            result = func(*args, **kwargs)

            return ThreadResponse(
                request_id=request.request_id,
                success=True,
                result=result
            )
        else:
            return ThreadResponse(
                request_id=request.request_id,
                success=False,
                error=f"Function {func_name} not found in kis_api"
            )

    except Exception as e:
        logging.error(f"[KIS Thread] API call {func_name} failed: {e}")
        return ThreadResponse(
            request_id=request.request_id,
            success=False,
            error=str(e)
        )

def _kis_thread_loop():
    """
    Main loop for the KIS Thread.

    Processes requests from kis_request_queue and sends responses
    to kis_response_queue.
    """
    logging.info("[KIS Thread] Starting main loop")
    update_kis_state(thread_status=ThreadStatus.RUNNING)

    while not _stop_event.is_set():
        try:
            # Wait for request with timeout to allow checking stop_event
            request = kis_request_queue.get(timeout=0.5)

            logging.debug(f"[KIS Thread] Processing request: {request.request_id} ({request.request_type.value})")

            response = _handle_request(request)
            kis_response_queue.put(response)

            logging.debug(f"[KIS Thread] Completed request: {request.request_id}")

        except Empty:
            # No request in queue, continue loop
            continue
        except Exception as e:
            logging.error(f"[KIS Thread] Unexpected error in main loop: {e}")
            update_kis_state(last_error=str(e))

    logging.info("[KIS Thread] Main loop stopped")
    update_kis_state(thread_status=ThreadStatus.STOPPED)


def start_kis_thread() -> bool:
    """
    Start the KIS Thread.

    Returns:
        True if thread started successfully, False otherwise
    """
    global _kis_thread, _stop_event

    if _kis_thread is not None and _kis_thread.is_alive():
        logging.warning("[KIS Thread] Already running")
        return False

    _stop_event.clear()
    update_kis_state(thread_status=ThreadStatus.STARTING)

    _kis_thread = threading.Thread(target=_kis_thread_loop, daemon=True, name="KISThread")
    _kis_thread.start()

    logging.info("[KIS Thread] Started")
    return True


def stop_kis_thread() -> None:
    """Stop the KIS Thread gracefully."""
    global _kis_thread

    if _kis_thread is None or not _kis_thread.is_alive():
        return

    logging.info("[KIS Thread] Stopping...")
    _stop_event.set()
    _kis_thread.join(timeout=5.0)

    if _kis_thread.is_alive():
        logging.warning("[KIS Thread] Did not stop gracefully")
    else:
        logging.info("[KIS Thread] Stopped")

    _kis_thread = None


def is_kis_thread_running() -> bool:
    """Check if the KIS Thread is running."""
    return _kis_thread is not None and _kis_thread.is_alive()


# =============================================================================
# Convenience Functions for Main Thread
# =============================================================================

def request_kis_auth() -> str:
    """
    Request KIS REST API authentication.

    Returns:
        request_id for tracking
    """
    request = ThreadRequest(request_type=RequestType.KIS_AUTH)
    kis_request_queue.put(request)
    return request.request_id


def request_kis_ws_auth() -> str:
    """
    Request KIS WebSocket authentication.

    Returns:
        request_id for tracking
    """
    request = ThreadRequest(request_type=RequestType.KIS_WS_AUTH)
    kis_request_queue.put(request)
    return request.request_id


def request_portfolio(force_refresh: bool = False) -> str:
    """
    Request portfolio data.

    Args:
        force_refresh: If True, bypass cache

    Returns:
        request_id for tracking
    """
    request = ThreadRequest(
        request_type=RequestType.GET_PORTFOLIO,
        kwargs={"force_refresh": force_refresh}
    )
    kis_request_queue.put(request)
    return request.request_id


def wait_for_response(request_id: str, timeout: float = 30.0) -> Optional[ThreadResponse]:
    """
    Wait for a response matching the given request_id.

    Args:
        request_id: The ID of the request to wait for
        timeout: Maximum time to wait in seconds

    Returns:
        ThreadResponse if found, None if timeout
    """
    start_time = time.time()
    pending_responses = []

    while (time.time() - start_time) < timeout:
        try:
            response = kis_response_queue.get(timeout=0.5)

            if response.request_id == request_id:
                # Put back any responses we collected
                for r in pending_responses:
                    kis_response_queue.put(r)
                return response
            else:
                # Not our response, save for later
                pending_responses.append(response)

        except Empty:
            continue

    # Timeout - put back collected responses
    for r in pending_responses:
        kis_response_queue.put(r)

    return None
