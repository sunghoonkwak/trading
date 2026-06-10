"""
Simplified display module - scroll-based terminal output.
All ANSI cursor control removed for reliable log visibility.
Orders are sent to Event Viewer via Unix domain socket IPC.
"""
import sys
import logging
from datetime import datetime

# Try to import event_pipe for order forwarding
# Lazy loaded event_pipe
_event_pipe_module = None
_pipe_import_attempted = False

def _get_event_pipe():
    global _event_pipe_module, _pipe_import_attempted
    if _event_pipe_module:
        return _event_pipe_module

    if _pipe_import_attempted:
        return None

    try:
        from core import event_pipe
        _event_pipe_module = event_pipe
        return _event_pipe_module
    except ImportError:
        pass # Silent fail is okay here, handled by caller or PIPE_AVAILABLE check
    except Exception:
        pass

    _pipe_import_attempted = True
    return None

# Colors (still useful for terminal output)
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_GRAY = "\033[90m"

from utils.format_utils import get_fixed_width

def add_alert(message: str, level: str = "INFO", time_str: str = None):
    """Print alert to terminal (simple scroll-based)."""
    timestamp = time_str if time_str else datetime.now().strftime("%H:%M:%S")

    logging.info(f"[Alert] [{level}] {message}")

    color = COLOR_GRAY
    if level == "ERROR":
        color = COLOR_RED
    elif level == "WARNING":
        color = COLOR_YELLOW
    elif level == "SUCCESS":
        color = COLOR_GREEN
    print(f"alert:[{timestamp}] {color}{message}{COLOR_RESET}")

    # Also send to web dashboard via event_pipe if available
    pipe = _get_event_pipe()
    if pipe:
        pipe.send_log("ALT", f"[{level}] {message}", time_str)

def update_order_state(order_id: str, ticker: str, name: str, side: str,
                       price: str, qty: str, state: str, notify: bool = True, time_str: str = None):
    """Send order update to Event Viewer via IPC.

    Format: ODR|ticker|name|side|qty|price|state|order_id
    """
    pipe = _get_event_pipe()
    if pipe:
        # Include name for display in viewer
        fixed_name = get_fixed_width(name, 20)
        order_msg = f"{fixed_name}|{ticker}|{side}|{qty}|{price}|{state}|{order_id}"
        pipe.send_log("ODR", order_msg, time_str)

    if notify:
        add_alert(f"{side} {ticker} {qty} @ {price} [{state}]", "INFO", time_str)


def remove_order_state(order_id: str):
    """Remove order (send REMOVED state to viewer)."""
    pipe = _get_event_pipe()
    if pipe:
        pipe.send_log("ODR", f"REMOVED|{order_id}")

def clear_order_states():
    """Clear all orders in Event Viewer."""
    pipe = _get_event_pipe()
    if pipe:
        pipe.send_log("CLR", "ORDERS")

def clear_quotes():
    """Clear all quotes in Event Viewer."""
    pipe = _get_event_pipe()
    if pipe:
        pipe.send_log("CLR", "QUOTES")


def show_in_result_area(lines):
    """Print lines to terminal (scroll-based)."""
    print("")
    for line in lines:
        print(line)


def input_at(row, col, prompt):
    """Simple input (ignore row/col in scroll mode)."""
    return input(prompt)


def safe_write(text):
    """Write text to stdout."""
    sys.stdout.write(text)
    sys.stdout.flush()
