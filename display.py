"""
Simplified display module - scroll-based terminal output.
All ANSI cursor control removed for reliable log visibility.
Orders are sent to Event Viewer via Named Pipe.
"""
import sys
import sys
from datetime import datetime

# Try to import event_pipe for order forwarding
try:
    from kis import event_pipe
    PIPE_AVAILABLE = True
except ImportError:
    PIPE_AVAILABLE = False

# Log file path (overwritten by main.py)
log_file_path = "WebSocket_latest.log"

# Colors (still useful for terminal output)
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_GRAY = "\033[90m"

from utils import get_fixed_width

def add_alert(message: str, level: str = "INFO"):
    """Print alert to terminal (simple scroll-based)."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    color = COLOR_GRAY
    if level == "ERROR":
        color = COLOR_RED
    elif level == "WARNING":
        color = COLOR_YELLOW
    elif level == "SUCCESS":
        color = COLOR_GREEN
    print(f"alert:[{timestamp}] {color}{message}{COLOR_RESET}")


def update_order_state(order_id: str, ticker: str, name: str, side: str,
                       price: str, qty: str, state: str, notify: bool = True):
    """Send order update to Event Viewer via pipe.

    Format: ODR|ticker|name|side|qty|price|state|order_id
    """
    if PIPE_AVAILABLE:
        # Include name for display in viewer
        fixed_name = get_fixed_width(name, 20)
        order_msg = f"{fixed_name}|{ticker}|{side}|{qty}|{price}|{state}|{order_id}"
        event_pipe.send_log("ODR", order_msg)

    if notify:
        add_alert(f"{side} {ticker} {qty} @ {price} [{state}]", "INFO")


def remove_order_state(order_id: str):
    """Remove order (send REMOVED state to viewer)."""
    if PIPE_AVAILABLE:
        event_pipe.send_log("ODR", f"REMOVED|{order_id}")

def clear_order_states():
    """Clear all orders in Event Viewer."""
    if PIPE_AVAILABLE:
        event_pipe.send_log("CLR", "ORDERS")

def clear_quotes():
    """Clear all quotes in Event Viewer."""
    if PIPE_AVAILABLE:
        event_pipe.send_log("CLR", "QUOTES")


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
