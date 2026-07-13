# -*- coding: utf-8 -*-
"""Serialized KIS runtime worker infrastructure adapter."""

import logging
import threading
import time
from queue import Empty, Queue
from typing import Callable, Optional, TypeVar

from application.ports import CorrelationId, OperationResult
from infrastructure.kis.rest_client import RESTClient
from infrastructure.kis.worker_protocol import (
    RequestType,
    ThreadRequest,
    ThreadResponse,
    kis_request_queue,
    kis_response_queue,
)
from infrastructure.kis.ws_manager import WSManager

_kis_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_ws_manager = WSManager()
_alert_publisher: Optional[Callable[[str, str], None]] = None
_rest_api_enabled: Optional[Callable[[], bool]] = None
_state_publisher: Optional[Callable[[str], None]] = None
T = TypeVar("T")


def configure_alert_publisher(publisher: Optional[Callable[[str, str], None]]) -> None:
    """Inject event-pipe alert delivery at composition time."""
    global _alert_publisher
    _alert_publisher = publisher


def configure_rest_api_enabled(enabled: Optional[Callable[[], bool]]) -> None:
    """Inject the KIS REST feature flag at composition time."""
    global _rest_api_enabled
    _rest_api_enabled = enabled


def configure_state_publisher(publisher: Optional[Callable[[str], None]]) -> None:
    """Inject KIS worker lifecycle state delivery at composition time."""
    global _state_publisher
    _state_publisher = publisher


def _is_rest_api_enabled() -> bool:
    if _rest_api_enabled is None:
        return False
    try:
        return _rest_api_enabled()
    except Exception as error:
        logging.error("[KISWorker] REST feature flag failed: %s", error)
        return False


def _publish_alert(message: str, level: str) -> None:
    if _alert_publisher is None:
        return
    try:
        _alert_publisher(message, level)
    except Exception as error:
        logging.warning("[KISWorker] Alert publication failed: %s", error)


def _publish_lifecycle_state(status: str) -> None:
    if _state_publisher is None:
        return
    try:
        _state_publisher(status)
    except Exception as error:
        logging.warning("[KISWorker] State publication failed: %s", error)


def _handle_request(request: ThreadRequest) -> ThreadResponse:
    """Process incoming worker requests."""
    try:
        if request.cancelled:
            return None
        result = None
        if request.request_type == RequestType.KIS_AUTH:
            if not _is_rest_api_enabled():
                return ThreadResponse(
                    request.request_id,
                    success=False,
                    error="KIS REST API is disabled",
                )
            result = RESTClient.authenticate()
        elif request.request_type == RequestType.KIS_WS_AUTH:
            result = RESTClient.authenticate_ws()
        elif request.request_type == RequestType.KIS_READ:
            if request.operation is None:
                return ThreadResponse(
                    request.request_id,
                    success=False,
                    error="KIS read operation is missing",
                    correlation_id=request.correlation_id,
                )
            result = request.operation()
        else:
            return ThreadResponse(
                request.request_id,
                success=False,
                error=f"Unsupported: {request.request_type}",
            )

        return ThreadResponse(
            request.request_id,
            success=True,
            result=result,
            correlation_id=request.correlation_id,
        )

    except Exception as error:
        logging.error("[KISWorker] Request %s failed: %s", request.request_id, error)
        return ThreadResponse(
            request.request_id,
            success=False,
            error=str(error),
            correlation_id=request.correlation_id,
        )


def _kis_thread_loop():
    """Main execution loop for the KIS worker thread."""
    logging.info("[KISWorker] Starting main loop")
    _publish_lifecycle_state("running")

    while not _stop_event.is_set():
        try:
            request = kis_request_queue.get(timeout=0.5)
            response = _handle_request(request)
            if response is None:
                continue
            if request.cancelled:
                logging.info("[KISWorker] Discarded late response %s", request.request_id)
            elif request.response_queue is not None:
                request.response_queue.put(response)
            else:
                kis_response_queue.put(response)
        except Empty:
            continue
        except Exception as error:
            logging.error("[KISWorker] Loop error: %s", error)

    logging.info("[KISWorker] Loop stopped")
    _publish_lifecycle_state("stopped")


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
    _ws_manager.stop()
    _stop_event.set()
    if _kis_thread:
        _kis_thread.join(timeout=5.0)


def is_kis_thread_running() -> bool:
    return _kis_thread is not None and _kis_thread.is_alive()


def initialize_websocket_and_pipe() -> bool:
    """Initialize KIS websocket subscriptions and link the event pipe."""
    success = _ws_manager.initialize()
    if success:
        _publish_alert("[KIS] Event pipe linked", "SUCCESS")
    return success


def request_kis_auth() -> str:
    req = ThreadRequest(RequestType.KIS_AUTH)
    kis_request_queue.put(req)
    return req.request_id


def request_kis_ws_auth() -> str:
    req = ThreadRequest(RequestType.KIS_WS_AUTH)
    kis_request_queue.put(req)
    return req.request_id


def wait_for_response(request_id: str, timeout: float = 30.0) -> Optional[ThreadResponse]:
    """Poll the response queue for a matching response id."""
    start = time.time()
    stashed: list[ThreadResponse] = []
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


class WorkerSerializedKisOperations:
    """Serialized KIS read adapter with per-request response correlation."""

    def execute(
        self,
        operation: Callable[[], T],
        *,
        timeout: float = 30.0,
        correlation_id: CorrelationId | None = None,
    ) -> OperationResult[T]:
        response_queue: Queue[ThreadResponse] = Queue(maxsize=1)
        request = ThreadRequest(
            RequestType.KIS_READ,
            operation=operation,
            correlation_id=str(correlation_id) if correlation_id else None,
            response_queue=response_queue,
        )
        kis_request_queue.put(request)
        request_correlation = CorrelationId(
            request.correlation_id or request.request_id
        )
        try:
            response = response_queue.get(timeout=timeout)
        except Empty:
            request.cancelled = True
            return OperationResult(
                error="KIS operation timed out",
                correlation_id=request_correlation,
            )

        if not response.success:
            return OperationResult(
                error=response.error or "KIS operation failed",
                correlation_id=CorrelationId(
                    response.correlation_id or request_correlation
                ),
            )
        return OperationResult(
            value=response.result,
            correlation_id=CorrelationId(
                response.correlation_id or request_correlation
            ),
        )
