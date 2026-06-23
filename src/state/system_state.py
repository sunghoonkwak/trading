# -*- coding: utf-8 -*-
"""
System State Management Module

Tracks the lifecycle and authentication status of various system threads.
"""
import threading
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

class ThreadStatus(Enum):
    NOT_STARTED = "not_started"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    STOPPED = "stopped"

class AuthStatus(Enum):
    NOT_AUTHENTICATED = "not_authenticated"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    FAILED = "failed"
    EXPIRED = "expired"

class WebSocketStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"

@dataclass
class KISState:
    thread_status: ThreadStatus = ThreadStatus.NOT_STARTED
    auth_status: AuthStatus = AuthStatus.NOT_AUTHENTICATED
    ws_auth_status: AuthStatus = AuthStatus.NOT_AUTHENTICATED
    ws_status: WebSocketStatus = WebSocketStatus.DISCONNECTED
    last_error: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class TelegramState:
    thread_status: ThreadStatus = ThreadStatus.NOT_STARTED
    bot_connected: bool = False
    last_error: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.now)

class SystemStateManager:
    """Singleton manager for system-wide thread states."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SystemStateManager, cls).__new__(cls)
                cls._instance._kis = KISState()
                cls._instance._telegram = TelegramState()
        return cls._instance

    def update_kis(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._kis, k):
                    setattr(self._kis, k, v)
            self._kis.last_updated = datetime.now()

    def update_telegram(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._telegram, k):
                    setattr(self._telegram, k, v)
            self._telegram.last_updated = datetime.now()

    def get_kis(self) -> KISState:
        with self._lock:
            return self._kis

    def get_telegram(self) -> TelegramState:
        with self._lock:
            return self._telegram

# =============================================================================
# Runtime State Helpers
# =============================================================================
_manager = SystemStateManager()

def update_kis_state(**kwargs): _manager.update_kis(**kwargs)
def update_telegram_state(**kwargs): _manager.update_telegram(**kwargs)

def is_kis_ready() -> bool:
    s = _manager.get_kis()
    return s.thread_status == ThreadStatus.RUNNING and s.auth_status == AuthStatus.AUTHENTICATED
