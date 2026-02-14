# -*- coding: utf-8 -*-
"""
KIS Thread Module (Refactored)

Orchestrates KIS API interactions by coordinating RESTClient and WSManager.
"""
import logging
import threading
import time
from queue import Empty
from typing import Optional

from thread_comm import (
    kis_request_queue, kis_response_queue,
    ThreadRequest, ThreadResponse, RequestType
)
from state.system_state import ThreadStatus, update_kis_state
from kis.rest_client import RESTClient
from kis.ws_manager import WSManager

# Module-level singletons
_kis_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_ws_manager = WSManager()

def _handle_request(request: ThreadRequest) -> ThreadResponse:
    """Process incoming thread requests using RESTClient."""
    try:
        result = None
        if request.request_type == RequestType.KIS_AUTH:
            result = RESTClient.authenticate()
        elif request.request_type == RequestType.KIS_WS_AUTH:
            result = RESTClient.authenticate_ws()
        elif request.request_type == RequestType.GET_PORTFOLIO:
            result = RESTClient.get_portfolio()
        else:
            return ThreadResponse(request.request_id, success=False, error=f"Unsupported: {request.request_type}")

        return ThreadResponse(request.request_id, success=True, result=result)

    except Exception as e:
        logging.error(f"[KISThread] Request {request.request_id} failed: {e}")
        return ThreadResponse(request.request_id, success=False, error=str(e))

def _kis_thread_loop():
    """Main execution loop for KISThread."""
    logging.info("[KISThread] Starting main loop")
    update_kis_state(thread_status=ThreadStatus.RUNNING)

    while not _stop_event.is_set():
        try:
            request = kis_request_queue.get(timeout=0.5)
            response = _handle_request(request)
            kis_response_queue.put(response)
        except Empty:
            continue
        except Exception as e:
            logging.error(f"[KISThread] Loop error: {e}")

    logging.info("[KISThread] Loop stopped")
    update_kis_state(thread_status=ThreadStatus.STOPPED)

# =============================================================================
# Public Control API
# =============================================================================

def start_kis_thread() -> bool:
    """Starts the background thread."""
    global _kis_thread
    if _kis_thread and _kis_thread.is_alive():
        return False

    _stop_event.clear()
    _kis_thread = threading.Thread(target=_kis_thread_loop, daemon=True, name="KISThread")
    _kis_thread.start()
    return True

def stop_kis_thread():
    """Gracefully stops the thread."""
    _stop_event.set()
    if _kis_thread:
        _kis_thread.join(timeout=5.0)

def is_kis_thread_running() -> bool:
    return _kis_thread is not None and _kis_thread.is_alive()

def initialize_websocket_and_pipe() -> bool:
    """Delegates WebSocket initialization to WSManager."""
    from display import add_alert
    success = _ws_manager.initialize()
    if success:
        add_alert("[KIS] Event pipe linked", "SUCCESS")
    return success

# =============================================================================
# Convenience Request Wrappers
# =============================================================================

def request_kis_auth() -> str:
    req = ThreadRequest(RequestType.KIS_AUTH)
    kis_request_queue.put(req)
    return req.request_id

def request_kis_ws_auth() -> str:
    req = ThreadRequest(RequestType.KIS_WS_AUTH)
    kis_request_queue.put(req)
    return req.request_id

def request_portfolio(force_refresh: bool = False) -> str:
    req = ThreadRequest(RequestType.GET_PORTFOLIO, kwargs={"force_refresh": force_refresh})
    kis_request_queue.put(req)
    return req.request_id

def wait_for_response(request_id: str, timeout: float = 30.0) -> Optional[ThreadResponse]:
    """Polls the response queue for a matching ID."""
    start = time.time()
    stashed = []
    while (time.time() - start) < timeout:
        try:
            resp = kis_response_queue.get(timeout=0.5)
            if resp.request_id == request_id:
                for r in stashed: kis_response_queue.put(r)
                return resp
            stashed.append(resp)
        except Empty:
            continue
    for r in stashed: kis_response_queue.put(r)
    return None
