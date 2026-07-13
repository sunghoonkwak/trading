# -*- coding: utf-8 -*-
"""
Thread Communication Module

This module defines the communication infrastructure between threads:
- Request/Response dataclasses for inter-thread messaging
- Queue definitions for KIS, Telegram, and data flow
"""
from queue import Queue

from infrastructure.kis.worker_protocol import (
    RequestType,
    ThreadRequest,
    ThreadResponse,
    kis_request_queue,
    kis_response_queue,
)

__all__ = [
    "RequestType",
    "ThreadRequest",
    "ThreadResponse",
    "kis_request_queue",
    "kis_response_queue",
    "kis_status_queue",
    "data_queue",
    "telegram_request_queue",
    "telegram_response_queue",
]

# =============================================================================
# Global Queues
# =============================================================================

# Status updates from KIS Thread (auth status, ws connection, errors)
kis_status_queue: Queue[dict] = Queue()

# WebSocket data from KIS Thread to Main Thread
data_queue: Queue[dict] = Queue()

# Telegram Thread communication (requests go through Main)
telegram_request_queue: Queue[ThreadRequest] = Queue()
telegram_response_queue: Queue[ThreadResponse] = Queue()
