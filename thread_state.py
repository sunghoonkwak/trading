# -*- coding: utf-8 -*-
"""
Thread State Management Module

This module manages the status and state of all threads in the application:
- KIS Thread status (auth, websocket connection)
- Telegram Thread status
- Global flags for thread coordination
"""
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import threading


class ThreadStatus(Enum):
    """Status values for thread lifecycle."""
    NOT_STARTED = "not_started"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    STOPPED = "stopped"


class AuthStatus(Enum):
    """Status values for authentication."""
    NOT_AUTHENTICATED = "not_authenticated"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    FAILED = "failed"
    EXPIRED = "expired"


class WebSocketStatus(Enum):
    """Status values for WebSocket connection."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class KISThreadState:
    """
    State container for KIS Thread.

    Attributes:
        thread_status: Current thread lifecycle status
        auth_status: REST API authentication status
        ws_auth_status: WebSocket authentication status
        ws_status: WebSocket connection status
        last_error: Most recent error message
        last_updated: Timestamp of last state change
    """
    thread_status: ThreadStatus = ThreadStatus.NOT_STARTED
    auth_status: AuthStatus = AuthStatus.NOT_AUTHENTICATED
    ws_auth_status: AuthStatus = AuthStatus.NOT_AUTHENTICATED
    ws_status: WebSocketStatus = WebSocketStatus.DISCONNECTED
    last_error: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.now)

    def update(self, **kwargs) -> None:
        """Update state fields and timestamp."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_updated = datetime.now()


@dataclass
class TelegramThreadState:
    """
    State container for Telegram Thread.

    Attributes:
        thread_status: Current thread lifecycle status
        bot_connected: Whether bot is connected to Telegram
        last_error: Most recent error message
        last_updated: Timestamp of last state change
    """
    thread_status: ThreadStatus = ThreadStatus.NOT_STARTED
    bot_connected: bool = False
    last_error: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.now)

    def update(self, **kwargs) -> None:
        """Update state fields and timestamp."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_updated = datetime.now()


# =============================================================================
# Global Thread State Instances
# =============================================================================
_state_lock = threading.Lock()

kis_state = KISThreadState()
telegram_state = TelegramThreadState()


def get_kis_state() -> KISThreadState:
    """Get current KIS thread state (thread-safe read)."""
    with _state_lock:
        return kis_state


def update_kis_state(**kwargs) -> None:
    """Update KIS thread state (thread-safe write)."""
    with _state_lock:
        kis_state.update(**kwargs)


def get_telegram_state() -> TelegramThreadState:
    """Get current Telegram thread state (thread-safe read)."""
    with _state_lock:
        return telegram_state


def update_telegram_state(**kwargs) -> None:
    """Update Telegram thread state (thread-safe write)."""
    with _state_lock:
        telegram_state.update(**kwargs)


# =============================================================================
# Convenience Functions for Status Checks
# =============================================================================

def is_kis_ready() -> bool:
    """Check if KIS Thread is ready for trading operations."""
    state = get_kis_state()
    return (
        state.thread_status == ThreadStatus.RUNNING and
        state.auth_status == AuthStatus.AUTHENTICATED
    )


def is_kis_ws_connected() -> bool:
    """Check if WebSocket is connected."""
    state = get_kis_state()
    return state.ws_status == WebSocketStatus.CONNECTED


def is_telegram_ready() -> bool:
    """Check if Telegram bot is ready."""
    state = get_telegram_state()
    return (
        state.thread_status == ThreadStatus.RUNNING and
        state.bot_connected
    )


def get_status_summary() -> dict:
    """
    Get a summary of all thread statuses for UI display.

    Returns:
        dict with status information for each thread
    """
    kis = get_kis_state()
    tg = get_telegram_state()

    return {
        "kis": {
            "thread": kis.thread_status.value,
            "auth": kis.auth_status.value,
            "ws": kis.ws_status.value,
            "error": kis.last_error
        },
        "telegram": {
            "thread": tg.thread_status.value,
            "connected": tg.bot_connected,
            "error": tg.last_error
        }
    }
