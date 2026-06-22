# -*- coding: utf-8 -*-
"""Application worker for serialized KIS runtime operations."""

import logging
import threading
import time
from queue import Empty
from typing import Optional

from core.thread_comm import (
    kis_request_queue,
    kis_response_queue,
    ThreadRequest,
    ThreadResponse,
    RequestType,
)
from state.system_state import ThreadStatus, update_kis_state
from broker.kis_rest_client import RESTClient
from broker.kis_ws_manager import WSManager
from core.trading_config import is_kis_rest_api_enabled


_kis_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_ws_manager = WSManager()


def _handle_request(request: ThreadRequest) -> ThreadResponse:
    """Process incoming worker requests."""
    try:
        result = None
        if request.request_type == RequestType.KIS_AUTH:
            if not is_kis_rest_api_enabled():
                return ThreadResponse(
                    request.request_id,
                    success=False,
                    error="KIS REST API is disabled",
                )
            result = RESTClient.authenticate()
        elif request.request_type == RequestType.KIS_WS_AUTH:
            result = RESTClient.authenticate_ws()
        elif request.request_type == RequestType.GET_PORTFOLIO:
            from data.portfolio_integration import get_integrated_portfolio

            scope = request.kwargs.get("scope", "all")
            result = get_integrated_portfolio(scope=scope)
        else:
            return ThreadResponse(
                request.request_id,
                success=False,
                error=f"Unsupported: {request.request_type}",
            )

        return ThreadResponse(request.request_id, success=True, result=result)

    except Exception as e:
        logging.error("[KISWorker] Request %s failed: %s", request.request_id, e)
        return ThreadResponse(request.request_id, success=False, error=str(e))


def _kis_thread_loop():
    """Main execution loop for the KIS worker thread."""
    logging.info("[KISWorker] Starting main loop")
    update_kis_state(thread_status=ThreadStatus.RUNNING)

    while not _stop_event.is_set():
        try:
            request = kis_request_queue.get(timeout=0.5)
            response = _handle_request(request)
            kis_response_queue.put(response)
        except Empty:
            continue
        except Exception as e:
            logging.error("[KISWorker] Loop error: %s", e)

    logging.info("[KISWorker] Loop stopped")
    update_kis_state(thread_status=ThreadStatus.STOPPED)


def start_kis_thread() -> bool:
    """Start the background KIS worker thread."""
    global _kis_thread
    if _kis_thread and _kis_thread.is_alive():
        return False

    _stop_event.clear()
    _kis_thread = threading.Thread(
        target=_kis_thread_loop,
        daemon=True,
        name="KISWorker",
    )
    _kis_thread.start()
    return True


def stop_kis_thread():
    """Gracefully stop the KIS worker thread."""
    _stop_event.set()
    if _kis_thread:
        _kis_thread.join(timeout=5.0)


def is_kis_thread_running() -> bool:
    return _kis_thread is not None and _kis_thread.is_alive()


def initialize_websocket_and_pipe() -> bool:
    """Initialize KIS websocket subscriptions and link the event pipe."""
    from core.display import add_alert

    success = _ws_manager.initialize()
    if success:
        add_alert("[KIS] Event pipe linked", "SUCCESS")
    return success


def request_kis_auth() -> str:
    req = ThreadRequest(RequestType.KIS_AUTH)
    kis_request_queue.put(req)
    return req.request_id


def request_kis_ws_auth() -> str:
    req = ThreadRequest(RequestType.KIS_WS_AUTH)
    kis_request_queue.put(req)
    return req.request_id


def request_portfolio(force_refresh: bool = False, scope: str = "all") -> str:
    req = ThreadRequest(
        RequestType.GET_PORTFOLIO,
        kwargs={"force_refresh": force_refresh, "scope": scope},
    )
    kis_request_queue.put(req)
    return req.request_id


def wait_for_response(request_id: str, timeout: float = 30.0) -> Optional[ThreadResponse]:
    """Poll the response queue for a matching response id."""
    start = time.time()
    stashed = []
    while (time.time() - start) < timeout:
        try:
            response = kis_response_queue.get(timeout=0.5)
            if response.request_id == request_id:
                for item in stashed:
                    kis_response_queue.put(item)
                return response
            stashed.append(response)
        except Empty:
            continue
    for item in stashed:
        kis_response_queue.put(item)
    return None
