# -*- coding: utf-8 -*-
"""
KIS REST Client Module (Advanced)

Handles REST API requests with retry logic, error handling, and timeout management.
"""
import logging
import time
from typing import Dict, Any, Callable
from functools import wraps

from kis.kis_api import kis_auth as ka
from state.system_state import update_kis_state, AuthStatus

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
        update_kis_state(auth_status=AuthStatus.AUTHENTICATING)
        try:
            ka.auth()
            update_kis_state(auth_status=AuthStatus.AUTHENTICATED)
            logging.info("[RESTClient] REST API authentication successful")
            return {"status": "authenticated"}
        except Exception as e:
            update_kis_state(auth_status=AuthStatus.FAILED, last_error=str(e))
            raise KISAuthError(f"REST Auth failed: {e}")

    @staticmethod
    @retry_on_exception(max_retries=3, delay=2.0)
    def authenticate_ws() -> Dict[str, Any]:
        """Handle WebSocket authentication with retries."""
        update_kis_state(ws_auth_status=AuthStatus.AUTHENTICATING)
        try:
            ka.auth_ws()
            update_kis_state(ws_auth_status=AuthStatus.AUTHENTICATED)
            logging.info("[RESTClient] WebSocket authentication successful")
            return {"status": "ws_authenticated"}
        except Exception as e:
            update_kis_state(ws_auth_status=AuthStatus.FAILED, last_error=str(e))
            raise KISAuthError(f"WS Auth failed: {e}")
