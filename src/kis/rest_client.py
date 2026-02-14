# -*- coding: utf-8 -*-
"""
KIS REST Client Module

Handles REST API requests including authentication and portfolio data fetching.
"""
import logging
from typing import Dict, Any
from kis.kis_api import kis_auth as ka
from thread_state import update_kis_state, AuthStatus

class RESTClient:
    """Encapsulates KIS REST API operations."""

    @staticmethod
    def authenticate() -> Dict[str, Any]:
        """Handle REST API authentication."""
        update_kis_state(auth_status=AuthStatus.AUTHENTICATING)
        try:
            ka.auth()
            update_kis_state(auth_status=AuthStatus.AUTHENTICATED)
            logging.info("[RESTClient] REST API authentication successful")
            return {"status": "authenticated"}
        except Exception as e:
            update_kis_state(auth_status=AuthStatus.FAILED, last_error=str(e))
            logging.error(f"[RESTClient] REST API authentication failed: {e}")
            raise

    @staticmethod
    def authenticate_ws() -> Dict[str, Any]:
        """Handle WebSocket authentication."""
        update_kis_state(ws_auth_status=AuthStatus.AUTHENTICATING)
        try:
            ka.auth_ws()
            update_kis_state(ws_auth_status=AuthStatus.AUTHENTICATED)
            logging.info("[RESTClient] WebSocket authentication successful")
            return {"status": "ws_authenticated"}
        except Exception as e:
            update_kis_state(ws_auth_status=AuthStatus.FAILED, last_error=str(e))
            logging.error(f"[RESTClient] WebSocket authentication failed: {e}")
            raise

    @staticmethod
    def get_portfolio() -> Dict[str, Any]:
        """Fetch portfolio data using the existing get_portfolio utility."""
        try:
            from kis.get_portfolio import get_portfolio
            result = get_portfolio()
            if result.get("error"):
                raise Exception(result["error"])
            return result
        except Exception as e:
            logging.error(f"[RESTClient] Failed to fetch portfolio: {e}")
            raise
