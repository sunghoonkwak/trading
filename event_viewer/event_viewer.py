"""
Event Viewer - Real-time market data display.
Runs in a separate terminal window with sticky area (latest per ticker) and scrolling history.
"""
import sys
import os
import time
import json
import shutil
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
CLEAR_LINE = "\033[2K"

# Debug mode (set to True to enable debug logging)
DEBUG_MODE = False

# State
latest_logs = OrderedDict()
history_start_row = 5


def get_terminal_size():
    return shutil.get_terminal_size()


def load_stock_config():
    """Load stock configuration for colorization."""
    try:
        # 1. Try relative to this script (../stock_configuration.json)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "stock_configuration.json")

        if not os.path.exists(config_path):
            # 2. Try current working directory
            config_path = "stock_configuration.json"

        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def get_ansi_rgb(r, g, b, text):
    """Apply RGB color to text."""
    return f"\033[38;2;{r};{g};{b}m{text}{RESET}"


def colorize_log(log: str, stock_config: dict) -> str:
    """Apply color to log based on type and ticker."""
    parts = log.split("|")

    if "SYS" in log:
        return f"{CYAN}{log}{RESET}"

    if len(parts) >= 4:
        ticker = parts[3].strip()
        if len(ticker) > 6 and ticker[:4] in ["DNAS", "DNYS", "DAMS"]:
            ticker = ticker[4:]

        for market in ["KR", "US"]:
            stocks = stock_config.get(market, [])
            for stock in stocks:
                if stock.get("ticker") == ticker and "color" in stock:
                    r, g, b = stock["color"]
                    return get_ansi_rgb(r, g, b, log)

    if "ERROR" in log or "|REJ|" in log:
        return f"{RED}{log}{RESET}"
    elif "|MKT|" in log:
        return f"{GRAY}{log}{RESET}"
    elif "|ODR|" in log or "|EXE|" in log:
        return f"{GREEN}{log}{RESET}"

    return f"{YELLOW}{log}{RESET}"


def enable_ansi_colors():
    """Enable ANSI colors on Windows."""
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


def extract_composite_key(log: str):
    """Extract ticker_type key from log message."""
    code = None
    log_type = "MKT"

    parts = log.split("|")

    if len(parts) >= 4:
        ticker = parts[3].strip()
        if len(ticker) > 6 and ticker[:4] in ["DNAS", "DNYS", "DAMS"]:
            code = ticker[4:]
        else:
            code = ticker

    if "|MKT|" in log:
        log_type = "MKT"
    elif any(x in log for x in ["|ODR|", "|COR|", "|CAN|", "|EXE|", "|REJ|"]):
        log_type = "ODR"

    if code and code.replace(" ", ""):
        return f"{code.strip()}_{log_type}"
    return None


def set_scroll_region(top: int, bottom: int):
    """Set terminal scroll region."""
    sys.stdout.write(f"\033[{top};{bottom}r")
    sys.stdout.flush()


def reset_scroll_region():
    """Reset scroll region to full screen."""
    sys.stdout.write("\033[r")
    sys.stdout.flush()


def draw_header():
    """Draw header (called once at startup)."""
    cols, rows = get_terminal_size()
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.write("=" * min(cols, 60) + "\n")
    sys.stdout.write(" Event Viewer\n")
    sys.stdout.write("-" * min(cols, 60) + "\n")
    sys.stdout.flush()


def draw_sticky_area(stock_config: dict, debug_file=None):
    """Update sticky logs at fixed positions."""
    global history_start_row
    cols, rows = get_terminal_size()

    num_sticky = len(latest_logs)

    if debug_file:
        debug_file.write(f"--- DRAW STICKY ---\n")
        debug_file.write(f"num_sticky: {num_sticky}, keys: {list(latest_logs.keys())}\n")
        debug_file.flush()

    line_num = 4
    for key, log in list(latest_logs.items()):
        colored = colorize_log(log, stock_config)
        sys.stdout.write(f"\033[{line_num};1H{CLEAR_LINE}{colored}")
        line_num += 1

    sys.stdout.write(f"\033[{line_num};1H{CLEAR_LINE}{GRAY}" + "-" * min(cols, 60) + f"{RESET}")
    history_start_row = line_num
    sys.stdout.flush()


current_history_row = 10


def append_history_log(log: str, stock_config: dict):
    """Append log to scrolling history area."""
    global current_history_row
    cols, rows = get_terminal_size()
    colored = colorize_log(log, stock_config)

    if current_history_row < history_start_row + 1:
        current_history_row = history_start_row + 1

    set_scroll_region(history_start_row + 1, rows)

    if current_history_row <= rows:
        sys.stdout.write(f"\033[{current_history_row};1H{CLEAR_LINE}{colored}")
        current_history_row += 1
    else:
        sys.stdout.write(f"\033[{rows};1H\n{CLEAR_LINE}{colored}")

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
    draw_header()

    global current_history_row
    current_history_row = history_start_row

    debug_file = open("viewer_debug.log", "w", encoding="utf-8") if DEBUG_MODE else None

    last_draw_time = time.time()
    DRAW_INTERVAL = 0.1
    needs_redraw = False

    try:
        while True:
            log = event_pipe.receive_log(handle)
            if log is None:
                reset_scroll_region()
                print("\nMain program closed. Closing...")
                time.sleep(1)
                break

            key = extract_composite_key(log)

            if debug_file:
                debug_file.write(f"EVENT: key={key}, log={log[:60]}...\n")

            if key:
                latest_logs[key] = log
                if debug_file:
                    debug_file.write(f"sticky updated: {key}\n")
                needs_redraw = True

            current_time = time.time()
            if needs_redraw and (current_time - last_draw_time) >= DRAW_INTERVAL:
                draw_sticky_area(stock_config, debug_file)
                last_draw_time = current_time
                needs_redraw = False

            append_history_log(log, stock_config)

    except KeyboardInterrupt:
        reset_scroll_region()
        print("\nExiting...")
    finally:
        reset_scroll_region()
        if debug_file:
            debug_file.close()
        event_pipe.close_pipe_client(handle)


if __name__ == "__main__":
    main()
