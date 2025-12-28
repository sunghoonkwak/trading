"""
This module handles ANSI-based terminal UI rendering and colorized logging.
It focuses solely on display logic, separating from the trading business logic.
"""
import sys
import shutil
import re
import threading
import unicodedata
import os
import logging
from enum import IntEnum
from collections import deque
import trading_config

# UI and Logging Configuration
LOG_BUFFER_SIZE = 30
log_buffer = deque(maxlen=LOG_BUFFER_SIZE)
latest_logs = {} # Map[code, colored_log]
terminal_lock = threading.Lock()
log_file_path = "WebSocket_latest.log"  # Overwritten by main.py at startup

# ANSI Escape Codes for UI
SAVE_CURSOR = "\033[s"
RESTORE_CURSOR = "\033[u"
CLEAR_LINE = "\033[2K"
HOME = "\033[H"
CLEAR_SCREEN = "\033[2J"

# Menu Options (Mapped to main.py choice cases)
MENU_OPTIONS = [
    " 1. Account Info (Balance & Portfolio)",
    " 2. Place Order (Buy/Sell)",
    " 3. Manage Open Orders (Correct/Cancel)",
    " 0. Change Log Level", # Toggle
    " c. Clear Order Logs  q. Exit"
]

class PrintLevel(IntEnum):
    ERROR = 0
    INFO = 1
    DEBUG = 2
    MAX = 3

print_log_level = PrintLevel.INFO

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

def print_log(level, log):
    if level == PrintLevel.ERROR:
        logging.error(log)
    elif level == PrintLevel.INFO or level == PrintLevel.DEBUG:
        logging.info(log)

    global latest_logs
    if level <= print_log_level:
        # Extract Ticker and Type to create a composite key
        # Patterns: [MKT][Name] Ticker | ... OR [BUY][ODR] [Name] Ticker | ...
        code = None
        log_type = "MKT" # Default to Market

        # 1. Extract Ticker
        # Look for the string between the last closing bracket and the pipe.
        match_code = re.search(r"\]\s+([\w\d]+)\s+\|", log)
        if match_code:
            raw_code = match_code.group(1).strip()
            # Normalize code: Remove 4-char prefix if it's an overseas code (e.g. DNASNVDA -> NVDA)
            if len(raw_code) > 6 and raw_code[:4] in ["DNAS", "DNYS", "DAMS", "HKSE", "HNXS"]:
                code = raw_code[4:]
            else:
                code = raw_code

        # 2. Extract Type (MKT vs ODR/COR/CAN/EXE/REJ)
        if "[MKT]" in log:
            log_type = "MKT"
        elif any(x in log for x in ["[ODR]", "[COR]", "[CAN]", "[EXE]", "[REJ]"]):
            log_type = "ODR"

        colored_log = log
        if level == PrintLevel.ERROR:
            colored_log = f"\033[91m{log}\033[0m"
        elif level == PrintLevel.DEBUG:
            colored_log = f"\033[90m{log}\033[0m" # Gray for DEBUG
        elif level == PrintLevel.INFO:
            if code:
                # Use extracted code for coloring lookup
                colored_log = get_ansi_rgb(code, log)
                if colored_log == log and match_code: # Fallback using raw code
                    colored_log = get_ansi_rgb(match_code.group(1).strip(), log)
            else:
                colored_log = f"\033[93m{log}\033[0m" # Yellow for general INFO

        if code and level == PrintLevel.INFO:
            # Update the latest summary with COMPOSITE KEY
            # Key format: "NVDA_MKT" or "NVDA_ODR"
            composite_key = f"{code}_{log_type}"
            latest_logs[composite_key] = colored_log

        log_buffer.appendleft(colored_log)
        render_ui()

def clear_result_area():
    with terminal_lock:
        sys.stdout.write(SAVE_CURSOR)
        for r in range(1, 11):
            sys.stdout.write(f"\033[{r};1H{CLEAR_LINE}")
        sys.stdout.write(RESTORE_CURSOR)
        sys.stdout.flush()

def show_in_result_area(lines):
    with terminal_lock:
        sys.stdout.write(SAVE_CURSOR)
        for i, line in enumerate(lines):
            if i >= 10: break
            sys.stdout.write(f"\033[{i+1};1H{CLEAR_LINE}{line}")
        sys.stdout.write(RESTORE_CURSOR)
        sys.stdout.flush()

def clear_order_logs():
    global latest_logs
    # Remove keys ending with _ODR
    keys_to_remove = [k for k in latest_logs.keys() if k.endswith("_ODR")]
    for k in keys_to_remove:
        del latest_logs[k]
    render_ui()

def input_at(row, col, prompt):
    with terminal_lock:
        sys.stdout.write(f"\033[{row};{col}H{CLEAR_LINE}{prompt}")
        sys.stdout.flush()
    return input()

def render_ui(full_refresh=False):
    cols, rows = shutil.get_terminal_size()
    visible_logs_count = min(LOG_BUFFER_SIZE, max(1, rows - 14))

    with terminal_lock:
        sys.stdout.write(SAVE_CURSOR)

        if full_refresh:
            status_name = "ERROR" if print_log_level == PrintLevel.ERROR else "INFO" if print_log_level == PrintLevel.INFO else "DEBUG"

            sys.stdout.write(f"\033[1;1H{CLEAR_LINE}" + "=" * min(cols, 40))
            sys.stdout.write(f"\033[2;1H{CLEAR_LINE} KIS Real-time System (Log: {status_name})")
            sys.stdout.write(f"\033[3;1H{CLEAR_LINE}" + "=" * min(cols, 40))

            for i, opt in enumerate(MENU_OPTIONS):
                sys.stdout.write(f"\033[{i+4};1H{CLEAR_LINE}{opt}")

        sys.stdout.write(f"\033[12;1H{CLEAR_LINE}" + "=" * (cols - 1))
        sys.stdout.write(f"\033[13;1H{CLEAR_LINE} Recent Logs (Max: {visible_logs_count})")
        sys.stdout.write(f"\033[14;1H{CLEAR_LINE}" + "-" * (cols - 1))

        # 3. Print Logs from line 14 onwards
        display_list = []
        latest_msgs_list = list(latest_logs.values())
        latest_msgs_list.reverse()
        display_list.extend(latest_msgs_list)

        latest_set = set(latest_msgs_list)
        for msg in log_buffer:
            if msg not in latest_set:
                display_list.append(msg)
            if len(display_list) >= visible_logs_count:
                break

        for i in range(visible_logs_count):
            row = 15 + i
            if row >= rows: break
            content = display_list[i] if i < len(display_list) else ""
            sys.stdout.write(f"\033[{row};1H{CLEAR_LINE}{content}")

        sys.stdout.write(RESTORE_CURSOR)
        sys.stdout.flush()

def prepare_exit():
    """Move cursor to the bottom to prevent shell prompt from overwriting UI."""
    cols, rows = shutil.get_terminal_size()
    with terminal_lock:
        # Move to the last line of the terminal
        sys.stdout.write(f"\033[{rows};1H\n")
        sys.stdout.flush()
