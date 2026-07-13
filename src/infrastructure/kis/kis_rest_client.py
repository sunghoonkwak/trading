# -*- coding: utf-8 -*-
"""
KIS REST Client Module (Advanced)

Handles REST API requests with retry logic, error handling, and timeout management.
"""
import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

from infrastructure.kis.kis_api import kis_auth as ka

_state_publisher: Optional[Callable[[str, Optional[str]], None]] = None


def configure_state_publisher(
    publisher: Optional[Callable[[str, Optional[str]], None]],
) -> None:
    """Inject runtime KIS authentication state delivery at composition time."""
    global _state_publisher
    _state_publisher = publisher


def _publish_state(phase: str, error: Optional[str] = None) -> None:
    if _state_publisher is None:
        return
    try:
        _state_publisher(phase, error)
    except Exception as publish_error:
        logging.warning("[RESTClient] State publication failed: %s", publish_error)


class KISAPIError(Exception):
    """Base exception for KIS API errors."""
    pass

class KISAuthError(KISAPIError):
    """Raised when authentication fails."""
    pass

def retry_on_exception(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator to retry a function on failure with exponential backoff."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        logging.error(f"[RESTClient] Max retries reached for {func.__name__}: {e}")
                        raise
                    logging.warning(f"[RESTClient] {func.__name__} failed (attempt {retries}/{max_retries}): {e}. Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff
            return func(*args, **kwargs)
        return wrapper
    return decorator

class RESTClient:
    """Advanced KIS REST API Client with reliability features."""

    @staticmethod
    @retry_on_exception(max_retries=3, delay=2.0)
    def authenticate() -> Dict[str, Any]:
        """Handle REST API authentication with retries."""
        _publish_state("authenticating")
        try:
            ka.auth()
            _publish_state("authenticated")
            logging.info("[RESTClient] REST API authentication successful")
            return {"status": "authenticated"}
        except Exception as exc:
            _publish_state("failed", str(exc))
            raise KISAuthError(f"REST Auth failed: {exc}") from exc

    @staticmethod
    @retry_on_exception(max_retries=3, delay=2.0)
    def authenticate_ws() -> Dict[str, Any]:
        """Handle WebSocket authentication with retries."""
        _publish_state("ws_authenticating")
        try:
            ka.auth_ws()
            _publish_state("ws_authenticated")
            logging.info("[RESTClient] WebSocket authentication successful")
            return {"status": "ws_authenticated"}
        except Exception as exc:
            _publish_state("ws_failed", str(exc))
            raise KISAuthError(f"WS Auth failed: {exc}") from exc
