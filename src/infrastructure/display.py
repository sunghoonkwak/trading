"""Terminal and event-viewer display adapter."""
import logging
import sys
from datetime import datetime
from typing import Optional

from utils.format_utils import get_fixed_width

_event_pipe_module = None
_pipe_import_attempted = False


def _get_event_pipe():
    global _event_pipe_module, _pipe_import_attempted
    if _event_pipe_module:
        return _event_pipe_module

    if _pipe_import_attempted:
        return None

    try:
        from infrastructure import event_pipe

        _event_pipe_module = event_pipe
        return _event_pipe_module
    except ImportError:
        pass
    except Exception:
        pass

    _pipe_import_attempted = True
    return None


def _send_pipe_log(msg_type: str, message: str, time_str: Optional[str] = None):
    pipe = _get_event_pipe()
    send_log = getattr(pipe, "send_log", None) if pipe else None
    if send_log:
        send_log(msg_type, message, time_str)


COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_GRAY = "\033[90m"


def add_alert(message: str, level: str = "INFO", time_str: Optional[str] = None):
    """Print an alert and forward it to the event viewer when available."""
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
    _send_pipe_log("ALT", f"[{level}] {message}", time_str)


def update_order_state(
    order_id: str,
    ticker: str,
    name: str,
    side: str,
    price: str,
    qty: str,
    state: str,
    notify: bool = True,
    time_str: Optional[str] = None,
    broker: str = "KIS",
):
    """Send an order update to the event viewer via IPC."""
    fixed_name = get_fixed_width(name, 20)
    order_msg = f"{fixed_name}|{ticker}|{side}|{qty}|{broker}|{price}|{state}|{order_id}"
    _send_pipe_log("ODR", order_msg, time_str)

    if notify:
        add_alert(f"{side} {ticker} {qty} @ {price} [{state}]", "INFO", time_str)


def remove_order_state(order_id: str):
    """Remove an order from the event viewer."""
    _send_pipe_log("ODR", f"REMOVED|{order_id}")


def clear_order_states():
    """Clear all orders in the event viewer."""
    _send_pipe_log("CLR", "ORDERS")


def clear_quotes():
    """Clear all quotes in the event viewer."""
    _send_pipe_log("CLR", "QUOTES")


def show_in_result_area(lines):
    """Print result lines to the terminal."""
    print("")
    for line in lines:
        print(line)


def input_at(row, col, prompt):
    """Read terminal input; row and column are retained for compatibility."""
    return input(prompt)


def safe_write(text):
    """Write text to stdout."""
    sys.stdout.write(text)
    sys.stdout.flush()
