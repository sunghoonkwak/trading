"""
Event Viewer - Runs in a separate terminal window.
Uses ANSI Scroll Region to keep sticky area fixed and history area scrollable.
"""
import sys
import os
import time
import json
import shutil
import re
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import event_pipe

# ANSI Color Codes
RESET = "\033[0m"
GRAY = "\033[90m"
YELLOW = "\033[93m"
RED = "\033[91m"
GREEN = "\033[92m"
CYAN = "\033[96m"

# ANSI Cursor Control
SAVE_CURSOR = "\033[s"
RESTORE_CURSOR = "\033[u"
CLEAR_LINE = "\033[2K"

# State
latest_logs = OrderedDict()
history_start_row = 5  # Where history area begins (after header + sticky)


def get_terminal_size():
    return shutil.get_terminal_size()


def load_stock_config():
    config_path = os.path.join(os.path.dirname(__file__), "stock_config.json")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}


def get_ansi_rgb(r, g, b, text):
    return f"\033[38;2;{r};{g};{b}m{text}{RESET}"


def colorize_log(log: str, stock_config: dict) -> str:
    match = re.search(r"\]\s+([\w\d]+)\s+\|", log)

    if "[SYS]" in log:
        return f"{CYAN}{log}{RESET}"

    if match:
        ticker = match.group(1).strip()
        if len(ticker) > 6 and ticker[:4] in ["DNAS", "DNYS", "DAMS"]:
            ticker = ticker[4:]

        for market in ["KR", "US"]:
            stocks = stock_config.get(market, [])
            for stock in stocks:
                if stock.get("ticker") == ticker and "color" in stock:
                    r, g, b = stock["color"]
                    return get_ansi_rgb(r, g, b, log)

    if "[ERROR]" in log or "[REJ]" in log:
        return f"{RED}{log}{RESET}"
    elif "[MKT]" in log:
        return f"{GRAY}{log}{RESET}"
    elif "[ODR]" in log or "[EXE]" in log:
        return f"{GREEN}{log}{RESET}"

    return f"{YELLOW}{log}{RESET}"


def enable_ansi_colors():
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


def extract_composite_key(log: str):
    code = None
    log_type = "MKT"

    match = re.search(r"\]\s+([\w\d]+)\s+\|", log)
    if match:
        raw_code = match.group(1).strip()
        if len(raw_code) > 6 and raw_code[:4] in ["DNAS", "DNYS", "DAMS"]:
            code = raw_code[4:]
        else:
            code = raw_code

    if "[MKT]" in log:
        log_type = "MKT"
    elif any(x in log for x in ["[ODR]", "[COR]", "[CAN]", "[EXE]", "[REJ]"]):
        log_type = "ODR"

    if code:
        return f"{code}_{log_type}"
    return None


def set_scroll_region(top: int, bottom: int):
    """Set terminal scroll region (DECSTBM)."""
    sys.stdout.write(f"\033[{top};{bottom}r")
    sys.stdout.flush()


def reset_scroll_region():
    """Reset scroll region to full screen."""
    sys.stdout.write("\033[r")
    sys.stdout.flush()


def draw_sticky_area(stock_config: dict):
    """Draw header and sticky logs (fixed area)."""
    global history_start_row
    cols, rows = get_terminal_size()

    sys.stdout.write(SAVE_CURSOR)
    sys.stdout.write("\033[H")  # Home

    # Header
    sys.stdout.write(f"{CLEAR_LINE}" + "=" * min(cols, 60) + "\n")
    sys.stdout.write(f"{CLEAR_LINE} Event Viewer (Sticky: {len(latest_logs)})\n")
    sys.stdout.write(f"{CLEAR_LINE}" + "-" * min(cols, 60) + "\n")

    # Sticky logs
    for key, log in list(latest_logs.items()):
        colored = colorize_log(log, stock_config)
        sys.stdout.write(f"{CLEAR_LINE}{colored}\n")

    # Separator
    if len(latest_logs) > 0:
        sys.stdout.write(f"{CLEAR_LINE}" + "-" * 30 + " History " + "-" * 21 + "\n")

    # Update history start row
    history_start_row = 4 + len(latest_logs) + (1 if len(latest_logs) > 0 else 0)

    # Set scroll region for history area only
    set_scroll_region(history_start_row, rows)

    sys.stdout.write(RESTORE_CURSOR)
    sys.stdout.flush()


# Track current row for history
current_history_row = 10

def append_history_log(log: str, stock_config: dict):
    """Append a log to the history area (scrollable)."""
    global current_history_row
    cols, rows = get_terminal_size()
    colored = colorize_log(log, stock_config)

    if current_history_row < rows:
        # Still filling up - print at current row
        sys.stdout.write(f"\033[{current_history_row};1H{colored}")
        current_history_row += 1
    else:
        # Full - scroll by printing at bottom
        sys.stdout.write(f"\033[{rows};1H\n{colored}")

    sys.stdout.flush()


def main():
    enable_ansi_colors()
    print("Event Viewer starting...")
    print(f"Connecting to pipe: {event_pipe.PIPE_NAME}")

    handle = None
    retry_count = 0
    max_retries = 30

    while handle is None and retry_count < max_retries:
        handle = event_pipe.connect_pipe_client()
        if handle is None:
            retry_count += 1
            print(f"Waiting for main.py... ({retry_count}/{max_retries})")
            time.sleep(1)

    if handle is None:
        print("Failed to connect to main.py. Exiting.")
        return

    stock_config = load_stock_config()

    # Clear screen and setup
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

    # TEST: Add dummy sticky logs
    dummy_logs = [
        "[18:00:00] [MKT][삼성전자  ] 005930 | Bid:   71,900 | Last:   72,000 | Ask:   72,100",
        "[18:00:00] [MKT][NVDA    ] NVDA   | Bid:   140.20 | Last:   140.50 | Ask:   140.80",
        "[18:00:00] [MKT][SK하이닉스] 000660 | Bid:  178,000 | Last:  178,500 | Ask:  179,000",
        "[18:00:00] [MKT][AAPL    ] AAPL   | Bid:   195.00 | Last:   195.50 | Ask:   196.00",
    ]
    dummy_keys = ["005930_MKT", "NVDA_MKT", "000660_MKT", "AAPL_MKT"]
    for key, log in zip(dummy_keys, dummy_logs):
        latest_logs[key] = log

    draw_sticky_area(stock_config)

    # Initialize history row after sticky area
    global current_history_row
    current_history_row = history_start_row

    try:
        while True:
            log = event_pipe.receive_log(handle)
            if log is None:
                reset_scroll_region()
                print("\nMain program closed. Closing...")
                time.sleep(1)
                break

            key = extract_composite_key(log)

            if key:
                # Update sticky area
                latest_logs[key] = log
                latest_logs.move_to_end(key)
                draw_sticky_area(stock_config)
            else:
                # Non-ticker log goes to history
                append_history_log(log, stock_config)

    except KeyboardInterrupt:
        reset_scroll_region()
        print("\nExiting...")
    finally:
        reset_scroll_region()
        event_pipe.close_pipe_client(handle)


if __name__ == "__main__":
    main()
