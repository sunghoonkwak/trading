# -*- coding: utf-8 -*-
"""
Super Menu Module - Scroll-based terminal output version.

This module provides the top-level menu for thread initialization.
"""
import os
import sys
import time
import logging

from display import add_alert

from thread_state import (
    ThreadStatus, AuthStatus, WebSocketStatus,
    get_kis_state, get_telegram_state, is_kis_ready, is_telegram_ready
)
from thread_comm import kis_response_queue
from kis.kis_thread import (
    start_kis_thread, stop_kis_thread, is_kis_thread_running,
    request_kis_auth, request_kis_ws_auth, wait_for_response
)


# ANSI Color codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
DIM = "\033[2m"


def _get_status_icon(status) -> str:
    """Get colored status icon based on status value."""
    if isinstance(status, ThreadStatus):
        if status == ThreadStatus.RUNNING:
            return f"{GREEN}●{RESET}"
        elif status == ThreadStatus.STARTING:
            return f"{YELLOW}◐{RESET}"
        elif status == ThreadStatus.ERROR:
            return f"{RED}✗{RESET}"
        else:
            return f"{DIM}○{RESET}"

    elif isinstance(status, AuthStatus):
        if status == AuthStatus.AUTHENTICATED:
            return f"{GREEN}✓{RESET}"
        elif status == AuthStatus.AUTHENTICATING:
            return f"{YELLOW}…{RESET}"
        elif status == AuthStatus.FAILED:
            return f"{RED}✗{RESET}"
        else:
            return f"{DIM}○{RESET}"

    elif isinstance(status, WebSocketStatus):
        if status == WebSocketStatus.CONNECTED:
            return f"{GREEN}✓{RESET}"
        elif status in [WebSocketStatus.CONNECTING, WebSocketStatus.RECONNECTING]:
            return f"{YELLOW}…{RESET}"
        elif status == WebSocketStatus.ERROR:
            return f"{RED}✗{RESET}"
        else:
            return f"{DIM}○{RESET}"

    return f"{DIM}?{RESET}"


def _print_super_menu():
    """Print super menu (scroll-based, no ANSI clearing)."""
    kis = get_kis_state()
    tg = get_telegram_state()

    # Status icons
    kis_icon = _get_status_icon(kis.thread_status)
    auth_icon = _get_status_icon(kis.auth_status)
    ws_auth_icon = _get_status_icon(kis.ws_auth_status)
    ws_conn_icon = _get_status_icon(kis.ws_status)
    tg_icon = _get_status_icon(tg.thread_status)

    # Build menu options based on status
    opt1 = f"{GREEN}[1] Telegram Init (Ready){RESET}" if is_telegram_ready() else f"{CYAN}[1] Telegram Init{RESET}"
    opt2 = f"{GREEN}[2] KIS Init (Ready){RESET}" if is_kis_ready() else f"{CYAN}[2] KIS API Init{RESET}"
    opt3 = f"{GREEN}[3] Start Trading{RESET}" if is_kis_ready() else f"{DIM}[3] Start Trading (Requires KIS){RESET}"

    # Print with leading newline for separation
    print(f"""
{'=' * 60}
 {BOLD}Thread Initialization Menu{RESET}
{'=' * 60}
 {kis_icon} KIS: {kis.thread_status.value:<12} | Auth: {auth_icon} {kis.auth_status.value:<15}
    WS Auth: {ws_auth_icon} {kis.ws_auth_status.value:<12} | Conn: {ws_conn_icon} {kis.ws_status.value}
 {tg_icon} Telegram: {tg.thread_status.value:<12} | Bot: {'Connected' if tg.bot_connected else 'Not connected'}
{'-' * 60}
 {opt1}
 {opt2}
 {opt3}
""")


def _init_kis_thread():
    """Initialize KIS Thread and perform authentication."""
    add_alert("[Super] Starting KIS Thread...", "INFO")

    if not is_kis_thread_running():
        if not start_kis_thread():
            add_alert("[Super] Failed to start KIS Thread", "ERROR")
            time.sleep(1)
            return
        # Give a small delay for thread to spin up
        time.sleep(0.5)

    if is_kis_ready():
        add_alert("[Super] KIS Thread is already running and ready", "WARNING")
        time.sleep(1)
        return

    time.sleep(0.5)

    add_alert("[Super] Authenticating REST API...", "INFO")
    auth_id = request_kis_auth()
    response = wait_for_response(auth_id, timeout=30.0)

    if response and response.success:
        add_alert("[Super] REST API auth successful", "SUCCESS")
    else:
        error = response.error if response else "Timeout"
        add_alert(f"[Super] REST Auth failed: {error}", "ERROR")
        time.sleep(2)
        return

    add_alert("[Super] Authenticating WebSocket...", "INFO")
    ws_auth_id = request_kis_ws_auth()
    response = wait_for_response(ws_auth_id, timeout=30.0)

    if response and response.success:
        add_alert("[Super] WebSocket auth successful", "SUCCESS")
    else:
        error = response.error if response else "Timeout"
        add_alert(f"[Super] WS Auth failed: {error}", "ERROR")
        time.sleep(2)
        return

    add_alert("[Super] Starting WebSocket & Event Pipe...", "INFO")
    from kis.kis_thread import initialize_websocket_and_pipe
    if initialize_websocket_and_pipe():
        add_alert("[Super] KIS Thread fully initialized!", "SUCCESS")
    else:
        add_alert("[Super] WS/Pipe init had issues", "WARNING")

    time.sleep(1)


def _init_telegram_thread():
    """Initialize Telegram Thread."""
    from thread_state import update_telegram_state

    add_alert("[Super] Starting Telegram Bot...", "INFO")

    if is_telegram_ready():
        add_alert("[Super] Telegram Bot is already running", "WARNING")
        time.sleep(1)
        return

    update_telegram_state(thread_status=ThreadStatus.STARTING)

    try:
        from telegram_bot.telegram_bot import initialize_telegram

        if initialize_telegram():
            update_telegram_state(
                thread_status=ThreadStatus.RUNNING,
                bot_connected=True
            )
            add_alert("[Super] Telegram Bot started", "SUCCESS")
        else:
            update_telegram_state(
                thread_status=ThreadStatus.ERROR,
                last_error="Failed to initialize"
            )
            add_alert("[Super] Telegram init failed", "ERROR")

    except Exception as e:
        update_telegram_state(
            thread_status=ThreadStatus.ERROR,
            last_error=str(e)
        )
        add_alert(f"[Super] Telegram error: {str(e)}", "ERROR")

    time.sleep(1)


def super_menu():
    """Main super menu loop."""
    while True:
        _print_super_menu()

        try:
            choice = input("Enter choice (Q: Exit): ").strip().lower()
        except KeyboardInterrupt:
            add_alert("[Super] Keyboard interrupt, exiting...", "INFO")
            break
        except EOFError:
            break

        if choice == '1':
            _init_telegram_thread()

        elif choice == '2':
            _init_kis_thread()

        elif choice == '3':
            if is_kis_ready():
                from menu.menu import menu
                menu()
            else:
                add_alert("[Super] KIS auth required first", "WARNING")
                time.sleep(1)

        elif choice == 'q':
            add_alert("[Super] Shutting down...", "INFO")
            stop_kis_thread()

            try:
                from telegram_bot.telegram_bot import shutdown_telegram
                shutdown_telegram()
            except:
                pass

            # Close event viewer
            try:
                from event_viewer import close_viewer
                close_viewer()
            except:
                pass

            break

        else:
            pass

    add_alert("[Super] Goodbye!", "INFO")


if __name__ == "__main__":
    super_menu()
