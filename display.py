"""
This module handles ANSI-based terminal UI rendering and colorized logging.
It focuses solely on display logic, separating from the trading business logic.

REFACTORED: Now sends WebSocket logs to separate terminal via Named Pipe,
and displays order status + alerts in main terminal.
"""
import sys
import shutil
import re
import threading
import unicodedata
import os
import logging

from datetime import datetime
from collections import deque, OrderedDict
from queue import Queue
import trading_config
import fear_and_greed
import time

# Cache for Fear & Greed Index
_fg_cache = {"value": "Init", "last_update": 0}

def get_fear_and_greed_display():
    """
    Fetches Fear & Greed index safely with caching (10 min).
    Prevents blocking the UI thread with frequent network calls.
    """
    global _fg_cache

    try:
        now = time.time()
        # Update every 10 minutes (600 seconds) to avoid API spam/blocking
        if now - _fg_cache["last_update"] > 600:
            data = fear_and_greed.get()
            # value is typically float (e.g. 42.0), convert to int for display
            _fg_cache["value"] = int(data.value)
            _fg_cache["last_update"] = now
    except Exception:
        # On error, retain old value or show error indicator if needed
        if _fg_cache["value"] == "Init":
            _fg_cache["value"] = "Err"

    return _fg_cache["value"]


# Try to import event_pipe for separate terminal support
try:
    from kis import event_pipe
    from kis.event_pipe import PrintLevel
    PIPE_AVAILABLE = True
except ImportError:
    PIPE_AVAILABLE = False

# UI and Logging Configuration

terminal_lock = threading.Lock()
log_file_path = "WebSocket_latest.log"  # Overwritten by main.py at startup

# Order State Tracking
# Map[order_id, OrderInfo dict]
order_states = OrderedDict()
MAX_ORDER_DISPLAY = 10

# Alert buffer (show up to 15 recent alerts)
alert_buffer = deque(maxlen=15)

# Thread-safe queue for alerts from background threads (e.g., Telegram bot)
_pending_alerts: Queue = Queue()

# ANSI Escape Codes for UI
SAVE_CURSOR = "\033[s"
RESTORE_CURSOR = "\033[u"
CLEAR_LINE = "\033[2K"
HOME = "\033[H"
CLEAR_SCREEN = "\033[2J"

# Colors
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_GRAY = "\033[90m"

# Menu Options (Mapped to main.py choice cases) - EXPANDED by 3 lines
MENU_OPTIONS = [
    " 1. Account Info (Balance & Portfolio)",
    " 2. Place Order (Buy/Sell)",
    " 3. Manage Open Orders (Correct/Cancel)",
    " r. RAOEO Strategy",
    " p. Portfolio",
    " ",
    " c. Clear All & Sync",
    " q. Exit"
]



def get_fixed_width_name(name, width=8):
    current_width = 0
    result = ""
    for char in name:
        w = 2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
        if current_width + w > width:
            break
        result += char
        current_width += w
    return result + (" " * (width - current_width))

def get_ansi_rgb(code, text):
    cfg = trading_config.get_stock_info(code)
    if cfg and "color" in cfg:
        r, g, b = cfg["color"]
        return f"\033[38;2;{r};{g};{b}m{text}\033[0m"
    return text


def safe_write(text):
    with terminal_lock:
        sys.stdout.write(text)
        sys.stdout.flush()





def update_order_state(order_id: str, ticker: str, name: str, side: str,
                       price: str, qty: str, state: str, notify: bool = True):
    """Update order state for display in main terminal."""
    order_states[order_id] = {
        "ticker": ticker,
        "name": name,
        "side": side,
        "price": price,
        "qty": qty,
        "state": state  # PLACED, EXECUTED, CANCELED, CORRECTING
    }
    # Move to end (most recent)
    order_states.move_to_end(order_id)

    if notify:
        # Add to alert buffer
        msg = f"{side} {ticker} {qty} @ {price} [{state}]"
        add_alert(msg, level="INFO")

    render_ui()


def add_alert(message: str, level: str = "INFO"):
    """
    Queue an alert message for display.
    This is thread-safe and should be used by all modules.
    """
    _pending_alerts.put((message, level))


def _add_alert_internal(message: str, level: str = "INFO"):
    """
    Actually adds alert to the buffer.
    Should ONLY be called by the alert processor (main thread context).
    """
    color = COLOR_YELLOW
    if level == "ERROR":
        color = COLOR_RED
    elif level == "SUCCESS":
        color = COLOR_GREEN

    timestamp = datetime.now().strftime("%H:%M:%S")
    alert_buffer.appendleft(f"[{timestamp}] {color}{message}{COLOR_RESET}")


def process_pending_alerts():
    """
    Process pending alerts from the queue.
    """
    processed = False
    while not _pending_alerts.empty():
        try:
            message, level = _pending_alerts.get_nowait()
            _add_alert_internal(message, level)
            processed = True
        except Exception:
            break
    return processed


# Background alert processor thread
_alert_processor_running = False


def _alert_processor_loop():
    """Background loop that processes pending alerts and refreshes UI."""
    global _alert_processor_running
    while _alert_processor_running:
        if process_pending_alerts():
            render_ui()
        time.sleep(0.5)  # Check every 500ms


def start_alert_processor():
    """Start background thread to process alerts from other threads."""
    global _alert_processor_running
    if _alert_processor_running:
        return  # Already running

    _alert_processor_running = True
    processor_thread = threading.Thread(target=_alert_processor_loop, daemon=True)
    processor_thread.start()


def stop_alert_processor():
    """Stop the background alert processor."""
    global _alert_processor_running
    _alert_processor_running = False


def clear_all_display_data():
    """Clear all order states and alerts from display."""
    global order_states, alert_buffer
    order_states.clear()
    alert_buffer.clear()
    render_ui()

def clear_order_states():
    """Clear only the order states (for syncing)."""
    global order_states
    order_states.clear()
    render_ui()

def remove_order_state(order_id: str):
    """Remove a specific order from the display state."""
    if order_id in order_states:
        del order_states[order_id]
        render_ui()


def clear_result_area():
    with terminal_lock:
        sys.stdout.write(SAVE_CURSOR)
        for r in range(1, 15):
            sys.stdout.write(f"\033[{r};1H{CLEAR_LINE}")
        sys.stdout.write(RESTORE_CURSOR)
        sys.stdout.flush()


def show_in_result_area(lines):
    """Display multiple lines in the top (1-14) area, clearing everything first."""
    with terminal_lock:
        sys.stdout.write(SAVE_CURSOR)
        for i in range(14):
            line = lines[i] if i < len(lines) else ""
            sys.stdout.write(f"\033[{i+1};1H{CLEAR_LINE}{line}")
        sys.stdout.write(RESTORE_CURSOR)
        sys.stdout.flush()


def clear_order_logs():
    """Alias for clear_all_display_data for backward compatibility."""
    clear_all_display_data()


def input_at(row, col, prompt):
    with terminal_lock:
        sys.stdout.write(f"\033[{row};{col}H{CLEAR_LINE}{prompt}")
        sys.stdout.flush()
    return input()


def _format_order_line(info: dict, cols: int) -> str:
    """Format a single order line for display."""
    ticker = info["ticker"][:6].ljust(6)
    name = get_fixed_width_name(info["name"], 24)
    side_text = info["side"]
    side = f"{side_text:<6}"
    price = info["price"][:8].rjust(8)
    qty = info["qty"][:4].rjust(4)

    # Active orders are shown in Yellow
    color = COLOR_YELLOW

    line = f"{ticker}:{name} | {side} prc:{price} qty:{qty}"
    return f"{color}{line}{COLOR_RESET}"


def render_ui(full_refresh=False):
    cols, rows = shutil.get_terminal_size()

    # Layout:
    # Row 1-3: Header
    # Row 4-11: Menu (8 lines)
    # Row 12: Separator
    # Row 13: "Enter Choice:" input (handled by menu.py)
    # Row 14+: Orders and Alerts

    order_area_start = 14
    available_rows = max(1, rows - order_area_start)

    with terminal_lock:
        sys.stdout.write(SAVE_CURSOR)

        if full_refresh:
            status_name = "ERROR" if event_pipe.get_log_level() == PrintLevel.ERROR else "INFO" if event_pipe.get_log_level() == PrintLevel.INFO else "DEBUG"

            sys.stdout.write(f"\033[1;1H{CLEAR_LINE}" + "=" * min(cols, 60))
            sys.stdout.write(f"\033[2;1H{CLEAR_LINE} KIS Real-time System (Log: {status_name}) (fear & greed: {get_fear_and_greed_display()})")
            sys.stdout.write(f"\033[3;1H{CLEAR_LINE}" + "=" * min(cols, 60))

            for i, opt in enumerate(MENU_OPTIONS):
                sys.stdout.write(f"\033[{i+4};1H{CLEAR_LINE}{opt}")

            # Separators around input area
            sys.stdout.write(f"\033[12;1H{CLEAR_LINE}" + "-" * min(cols - 1, 60))
            # Row 13 is for input - handled by menu.py

        # Display orders (most recent first)
        order_list = list(order_states.items())
        order_list.reverse()

        row = order_area_start
        displayed = 0

        # Display orders separator
        sys.stdout.write(f"\033[{row};1H{CLEAR_LINE}" + "-" * 26 + " Orders " + "-" * 26)
        row += 1

        # Show orders
        for _, info in order_list[:MAX_ORDER_DISPLAY]:
            if row >= rows:
                break
            line = _format_order_line(info, cols)
            sys.stdout.write(f"\033[{row};1H{CLEAR_LINE}{line}")
            row += 1
            displayed += 1

        sys.stdout.write(f"\033[{row};1H{CLEAR_LINE}" + "-" * 26 + " Alerts " + "-" * 26)
        row += 1

        # Show alerts after orders if space
        if displayed < available_rows and alert_buffer:
            for alert in list(alert_buffer)[:available_rows - displayed - 1]:
                if row >= rows:
                    break
                sys.stdout.write(f"\033[{row};1H{CLEAR_LINE}{alert}")
                row += 1

        # Clear remaining rows
        while row < rows:
            sys.stdout.write(f"\033[{row};1H{CLEAR_LINE}")
            row += 1

        sys.stdout.write(RESTORE_CURSOR)
        sys.stdout.flush()


def prepare_exit():
    """Move cursor to the bottom to prevent shell prompt from overwriting UI."""
    cols, rows = shutil.get_terminal_size()
    with terminal_lock:
        sys.stdout.write(f"\033[{rows};1H\n")
        sys.stdout.flush()
