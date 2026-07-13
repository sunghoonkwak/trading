"""Request and response protocol for the serialized KIS worker."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue
from typing import Any, Callable, Optional


class RequestType(Enum):
    """Types of requests that can be sent to the KIS worker."""

    KIS_AUTH = "kis_auth"
    KIS_WS_AUTH = "kis_ws_auth"
    KIS_READ = "kis_read"


@dataclass
class ThreadRequest:
    """Request object for KIS worker inter-thread communication."""

    request_type: RequestType
    func_name: str = ""
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    operation: Optional[Callable[[], Any]] = None
    correlation_id: Optional[str] = None
    response_queue: Any = None
    cancelled: bool = False
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ThreadResponse:
    """Response object matched to a KIS worker request."""

    request_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    correlation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


kis_request_queue: Queue[ThreadRequest] = Queue()
kis_response_queue: Queue[ThreadResponse] = Queue()
