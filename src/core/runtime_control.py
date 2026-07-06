# -*- coding: utf-8 -*-
"""Runtime control plane shared by Telegram commands and the main system."""

from dataclasses import dataclass
from threading import Lock
from typing import Callable, Optional


@dataclass
class RuntimeCommandResult:
    success: bool
    message: str
    component: Optional[str] = None
    already_in_state: bool = False


_lock = Lock()
_start_hook: Optional[Callable[[], RuntimeCommandResult]] = None
_stop_hook: Optional[Callable[[], RuntimeCommandResult]] = None
_status_hook: Optional[Callable[[], bool]] = None


def register_runtime_hooks(
    start_hook: Callable[[], RuntimeCommandResult],
    stop_hook: Callable[[], RuntimeCommandResult],
    status_hook: Callable[[], bool],
) -> None:
    """Register lifecycle hooks owned by the running TradingSystem instance."""
    global _start_hook, _stop_hook, _status_hook
    with _lock:
        _start_hook = start_hook
        _stop_hook = stop_hook
        _status_hook = status_hook


def start_runtime() -> RuntimeCommandResult:
    with _lock:
        hook = _start_hook
    if hook is None:
        return RuntimeCommandResult(
            success=False,
            message="Runtime controller is not ready.",
        )
    return hook()


def stop_runtime() -> RuntimeCommandResult:
    with _lock:
        hook = _stop_hook
    if hook is None:
        return RuntimeCommandResult(
            success=False,
            message="Runtime controller is not ready.",
        )
    return hook()


def is_runtime_running() -> bool:
    with _lock:
        hook = _status_hook
    return bool(hook and hook())
