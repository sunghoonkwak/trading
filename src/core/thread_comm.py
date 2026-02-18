# -*- coding: utf-8 -*-
"""
Thread Communication Module

This module defines the communication infrastructure between threads:
- Request/Response dataclasses for inter-thread messaging
- Queue definitions for KIS, Telegram, and data flow
"""
from queue import Queue
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from datetime import datetime
import uuid


class RequestType(Enum):
    """Types of requests that can be sent to KIS Thread."""
    KIS_AUTH = "kis_auth"
    KIS_WS_AUTH = "kis_ws_auth"
    GET_PORTFOLIO = "get_portfolio"


@dataclass
class ThreadRequest:
    """
    Request object for inter-thread communication.

    Attributes:
        request_id: Unique identifier for tracking request/response pairs
        request_type: Type of request (KIS_AUTH, KIS_WS_AUTH, etc.)
        func_name: Name of the function to call
        args: Positional arguments for the function
        kwargs: Keyword arguments for the function
        timestamp: When the request was created
    """
    request_type: RequestType
    func_name: str = ""
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ThreadResponse:
    """
    Response object for inter-thread communication.

    Attributes:
        request_id: Matches the original request's ID
        success: Whether the request was successful
        result: The result data (if successful)
        error: Error message (if failed)
        timestamp: When the response was created
    """
    request_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


# =============================================================================
# Global Queues
# =============================================================================

# KIS Thread communication
kis_request_queue: Queue[ThreadRequest] = Queue()
kis_response_queue: Queue[ThreadResponse] = Queue()

# Status updates from KIS Thread (auth status, ws connection, errors)
kis_status_queue: Queue[dict] = Queue()

# WebSocket data from KIS Thread to Main Thread
data_queue: Queue[dict] = Queue()

# Telegram Thread communication (requests go through Main)
telegram_request_queue: Queue[ThreadRequest] = Queue()
telegram_response_queue: Queue[ThreadResponse] = Queue()

