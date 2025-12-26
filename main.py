import logging
import pandas as pd
import kis_api.kis_auth as ka
import threading
import os
import sys
import shutil
from datetime import datetime
from enum import IntEnum
from collections import deque
import json
import msvcrt
import re
import unicodedata

# Configure logging with dynamic filename based on server start time
log_timestamp = datetime.now().strftime("%y_%m_%d_%H_%M_%S")
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"WebSocket_{log_timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
    ]
)

# Global flag for toggling real-time data printing
class PrintLevel(IntEnum):
    ERROR = 0
    INFO = 1
    DEBUG = 2
    MAX = 3

print_log_level = PrintLevel.INFO

def get_fixed_width_name(name, width=8):
    """
    Returns a string of the specified visual width.
    Korean characters are counted as 2 units, others as 1.
    """
    current_width = 0
    result = ""
    for char in name:
        # 'W'ide and 'F'ullwidth are typically 2 units in terminals
        w = 2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
        if current_width + w > width:
            break
        result += char
        current_width += w
    return result + (" " * (width - current_width))

# Load Stock Configuration from JSON
STOCK_CONFIG = {}
try:
    _json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_config.json")
    if os.path.exists(_json_path):
        with open(_json_path, "r", encoding="utf-8") as f:
            STOCK_CONFIG = json.load(f)
except Exception as e:
    pass

def get_ansi_rgb(code, text):
    """Wrap text in ANSI RGB color sequence if config exists"""
    cfg = STOCK_CONFIG.get(code)
    if cfg and "color" in cfg:
        r, g, b = cfg["color"]
        return f"\033[38;2;{r};{g};{b}m{text}\033[0m"
    return text

# UI Configuration
LOG_BUFFER_SIZE = 30
log_buffer = deque(maxlen=LOG_BUFFER_SIZE)
latest_logs = {} # Map[code, colored_log]
stock_data_state = {}
terminal_lock = threading.Lock()

# ANSI Escape Codes for UI
SAVE_CURSOR = "\033[s"
RESTORE_CURSOR = "\033[u"
CLEAR_LINE = "\033[2K"
HOME = "\033[H"
CLEAR_SCREEN = "\033[2J"
MOVE_TO_LOG_START = "\033[11;1H"

def safe_write(text):
    with terminal_lock:
        sys.stdout.write(text)
        sys.stdout.flush()

# Logging functions
def print_log(level, log):
    # 1. Record to file using standard logging module
    if level == PrintLevel.ERROR:
        logging.error(log)
    elif level == PrintLevel.INFO or level == PrintLevel.DEBUG:
        logging.info(log)

    # 2. Update Terminal UI if level matches
    global latest_logs
    if level <= print_log_level:
        code = None
        match = re.search(r"\] (([A-Z0-9]{6})|([0-9]{6})) \|", log)
        if match:
            code = match.group(1).strip()

        colored_log = log
        if level == PrintLevel.ERROR:
            colored_log = f"\033[91m{log}\033[0m" # Red
        elif level == PrintLevel.INFO:
            if code:
                colored_log = get_ansi_rgb(code, log)
            else:
                colored_log = f"\033[93m{log}\033[0m" # Fallback Yellow

        # Update latest logs per stock for the top section
        if code and level == PrintLevel.INFO:
            # Move to front of 'latest' section by re-inserting
            if code in latest_logs:
                del latest_logs[code]
            latest_logs[code] = colored_log

        # Add to historical buffer
        log_buffer.appendleft(colored_log)
        render_ui()

def render_ui(full_refresh=False):
    """
    Renders the entire UI (Menu + Logs) predictably.
    """
    cols, rows = shutil.get_terminal_size()

    # Calculate how many logs we can display (Budget: ~15 lines for menu and space, limited by buffer size)
    visible_logs_count = min(LOG_BUFFER_SIZE, max(1, rows - 16))

    with terminal_lock:
        # Save user's current input position
        sys.stdout.write(SAVE_CURSOR)

        if full_refresh:
            # Move to top and draw Menu Area
            sys.stdout.write(HOME)
            status_name = "ERROR" if print_log_level == PrintLevel.ERROR else "INFO" if print_log_level == PrintLevel.INFO else "DEBUG"

            menu_lines = [
                "=" * min(cols, 40),
                f" KIS Real-time System (Log: {status_name})",
                "=" * min(cols, 40),
                " 1. Get Cash Info (KRW/USD)",
                " 0. Change Log Level",
                " q. Exit",
                "-" * min(cols, 40),
                "Enter Choice: "
            ]
            for line in menu_lines:
                sys.stdout.write(f"{CLEAR_LINE}{line}\n")

            # 1.5 Clear any leftovers between menu end and log area (Line 9 & 10)
            for _ in range(2):
                sys.stdout.write(f"{CLEAR_LINE}\n")

        # 2. Jump to Log Area (Line 11)
        sys.stdout.write(MOVE_TO_LOG_START)
        sys.stdout.write(f"{CLEAR_LINE}\n" + "=" * (cols - 1) + "\n")
        sys.stdout.write(f"{CLEAR_LINE} Recent Logs (Max visible: {visible_logs_count}):\n")
        sys.stdout.write(f"{CLEAR_LINE}" + "-" * (cols - 1) + "\n")

        # 3. Print Logs
        # Build the prioritized display list:
        # First, the latest message from each stock (most recent stock first)
        display_list = []
        # latest_logs keys are updated such that most recent is last. Let's reverse for top.
        latest_msgs_list = list(latest_logs.values())
        latest_msgs_list.reverse()

        display_list.extend(latest_msgs_list)

        # Then, fill the rest with historical logs from buffer, excluding the ones already at top
        latest_set = set(latest_msgs_list)
        for msg in log_buffer:
            if msg not in latest_set:
                display_list.append(msg)
            if len(display_list) >= visible_logs_count:
                break

        for log in display_list[:visible_logs_count]:
            sys.stdout.write(f"{CLEAR_LINE}{log[:cols+100]}\n")

        # Clear remaining rows below logs up to terminal bottom to prevent ghosting
        for _ in range(max(0, rows - 15 - len(display_list))):
            sys.stdout.write(f"{CLEAR_LINE}\n")

        # 3. RETURN TO USER INPUT POSITION
        sys.stdout.write(RESTORE_CURSOR)
        sys.stdout.flush()

# Rename local PrintLevel to avoid some typing conflicts if any
PyPrintLevel = PrintLevel

def write_cleared(text, end="\n"):
    """Write text while clearing the current line"""
    safe_write(f"{CLEAR_LINE}{text}{end}")

def on_result(ws, tr_id, df: pd.DataFrame, dm: dict):
    """
    Callback function when data is received.
    """
    if df.empty:
        print_log(PrintLevel.ERROR, f"System Message received for TR: {tr_id}")
        return

    # Process all records in the DataFrame (KIS can send multiple updates in one message)
    for i in range(len(df)):
        row = df.iloc[i]
        code = row['MKSC_SHRN_ISCD']

        # Initialize state for code if not exists with all market fields
        if code not in stock_data_state:
            stock_data_state[code] = {
                'price': 0, 'ask': 0, 'bid': 0,
                'change': 0, 'rate': 0.0, 'vol': 0,
                'time': '000000'
            }

        state = stock_data_state[code]

        level = PrintLevel.DEBUG # Default level

        if tr_id == "H0UNASP0": # Stock Asking Price
            state['time'] = row['BSOP_HOUR']
            try:
                new_ask = int(float(row['ASKP1']))
                new_bid = int(float(row['BID_PRC1'] if 'BID_PRC1' in row else row['BIDP1']))

                # Skip if neither ask nor bid changed
                if state['ask'] == new_ask and state['bid'] == new_bid:
                    continue
                else:
                    level = PrintLevel.INFO

                state['ask'] = new_ask
                state['bid'] = new_bid
            except (ValueError, TypeError, KeyError):
                continue

        elif tr_id == "H0UNCNT0": # Stock Execution
            state['time'] = row['STCK_CNTG_HOUR']
            try:
                new_price = int(float(row['STCK_PRPR']))
                new_vol   = int(float(row['CNTG_VOL']))

                # Check for INFO level conditions: price change or large volume
                if state['price'] != new_price or new_vol >= 100:
                    level = PrintLevel.INFO

                state['price']  = new_price
                state['change'] = int(float(row['PRDY_VRSS']))
                state['rate']   = float(row['PRDY_CTRT'])
                state['vol']    = new_vol

                # Add sign to change for display
                # 1: Upper limit, 2: Up, 3: Flat, 4: Lower limit, 5: Down
                sign = row['PRDY_VRSS_SIGN']
                state['sign_str'] = "+" if sign in ['1', '2'] else "-" if sign in ['4', '5'] else " "
            except (ValueError, TypeError, KeyError):
                continue

        # Format values for the unified log
        time_v = state.get('time', '000000')
        time_s  = f"{time_v[:2]}:{time_v[2:4]}:{time_v[4:6]}"

        # Use fallback values if data hasn't arrived yet
        bid_s   = format(state.get('bid', 0), ",")
        ask_s   = format(state.get('ask', 0), ",")
        price_v = state.get('price', 0)
        price_s = format(price_v, ",") if price_v > 0 else "-------"
        vol_s   = format(state.get('vol', 0), ",")
        diff_s  = f"{state.get('sign_str', '')}{format(state.get('change', 0), ',')}"

        # [12:03:44] [SK하이닉스] 000660 | Bid:   178,500 | Last:   178,600 (     5) | Diff:    +5,800 ( 5.22%) | Ask:   12,300
        cfg = STOCK_CONFIG.get(code, {})
        name = cfg.get("name", "Unknown")
        fixed_name = get_fixed_width_name(name, 10)
        msg = (f"[{time_s}] [{fixed_name}] {code:<6} | "
               f"Bid: {bid_s:>9} | "
               f"Last: {price_s:>9} ({vol_s:>6}) | "
               f"Diff: {diff_s:>9} ({state.get('rate', 0.0):>5.2f}%) | "
               f"Ask: {ask_s:>9}")

        print_log(level, msg)

def inquire_combined_cash() -> list:
    """
    Inquire both Domestic (KRW) and Overseas (USD) Cash Info
    """
    lines = [
        "=" * 40,
        " [Account Cash Information]",
        "=" * 40,
    ]

    # 1. Domestic Info (KRW)
    cano = ka.getTREnv().my_acct
    acnt_prdt_cd = ka.getTREnv().my_prod

    params_krw = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "PDNO": "005930",
        "ORD_UNPR": "0",
        "ORD_DVSN": "01",
        "CMA_EVLU_AMT_ICLD_YN": "N",
        "OVRS_ICLD_YN": "N"
    }
    url_krw = "/uapi/domestic-stock/v1/trading/inquire-psbl-order"
    res_krw = ka._url_fetch(url_krw, "TTTC8908R", "N", params_krw)

    import json as json_lib # Import here to avoid global import if not used elsewhere

    if res_krw.isOK():
        body = res_krw.getBody()
        logging.info(f"--- Orderable Raw Response ---\n{json_lib.dumps(body._asdict(), indent=4, ensure_ascii=False)}")
        output = getattr(body, 'output', None)
        if isinstance(output, dict):
            deposit = output.get('ord_psbl_cash') or '0'
            orderable = output.get('nrcvb_buy_amt') or '0'
            lines.append(f" KRW Deposit     : {format(int(float(deposit)), ','):>12} KRW")
            lines.append(f" Orderable KRW   : {format(int(float(orderable)), ','):>12} KRW")
    else:
        lines.append(f" KRW Error       : {res_krw.getErrorMessage()}")

    lines.append("-" * 40)

    # 2. Overseas Info (USD)
    # TR_ID: CTRP6504R (Real), VTRP6504R (Demo)
    tr_id_usd = "CTRP6504R"

    params_usd = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "WCRC_FRCR_DVSN_CD": "02",
        "NATN_CD": "000",
        "TR_MKET_CD": "00",
        "INQR_DVSN_CD": "00"
    }
    url_usd = "/uapi/overseas-stock/v1/trading/inquire-present-balance"
    res_usd = ka._url_fetch(url_usd, tr_id_usd, "N", params_usd)

    if res_usd.isOK():
        body = res_usd.getBody()
        logging.info(f"--- Overseas Cash Raw Response ---\n{json_lib.dumps(body._asdict(), indent=4, ensure_ascii=False)}")

        # Robustly extract the first record from output2
        output2 = getattr(body, 'output2', None)
        data = None
        if isinstance(output2, list) and len(output2) > 0:
            data = output2[0]
        elif isinstance(output2, dict):
            data = output2

        if data:
            def _gv(o, k): return o.get(k, '0') if isinstance(o, dict) else getattr(o, k, '0')
            f_deposit = _gv(data, 'frcr_dncl_amt_2')
            f_withdrawable = _gv(data, 'frcr_drwg_psbl_amt_1')

            lines.append(f" USD Deposit     : {format(float(f_deposit), ',.2f'):>12} USD")
            lines.append(f" Withdrawable USD: {format(float(f_withdrawable), ',.2f'):>12} USD")
        else:
            lines.append(" USD Error       : Balance info not found in output2")
    else:
        lines.append(f" USD Error       : {res_usd.getErrorMessage()}")

    lines.append("-" * 40)
    lines.append(f" (Log: {os.path.basename(log_file)})")
    lines.append(" [Press any key to return to menu]")

    return lines

def menu():
    global print_log_level
    os.system('cls' if os.name == 'nt' else 'clear')
    render_ui(full_refresh=True)

    while True:
        render_ui(full_refresh=True)
        safe_write("\033[8;15H")

        choice = input()

        if choice == '1':
            lines = inquire_combined_cash()
            with terminal_lock:
                sys.stdout.write(SAVE_CURSOR)
                sys.stdout.write(HOME)
                # Print result area with a bit more buffer
                for line in lines:
                    sys.stdout.write(f"{CLEAR_LINE}{line}\n")
                # Clear more lines below to ensure no ghosting
                for _ in range(max(0, 15 - len(lines))):
                    sys.stdout.write(f"{CLEAR_LINE}\n")
                sys.stdout.write(RESTORE_CURSOR)
                sys.stdout.flush()
            msvcrt.getch()
            render_ui(full_refresh=True)
        elif choice == "0":
            print_log_level = (print_log_level + 1) % PrintLevel.MAX
        elif choice == 'q':
            cols, rows = shutil.get_terminal_size()
            sys.stdout.write(f"\033[{rows};1H\n")
            print("Exiting...")
            os._exit(0)
        else:
            pass

from kis_api.domestic_stock.asking_price_total.asking_price_total import asking_price_total
from kis_api.domestic_stock.ccnl_total.ccnl_total import ccnl_total

if __name__ == "__main__":
    print("=== KIS Real-time Trading System ===")

    ka.auth()
    ka.auth_ws()

    ws = ka.KISWebSocket(api_url="")

    # Load stocks to watch from config, filtering out disabled ones
    stocks_to_watch = [code for code, cfg in STOCK_CONFIG.items() if not cfg.get("disabled", False)]

    if stocks_to_watch:
        ws.subscribe(asking_price_total, stocks_to_watch)
        ws.subscribe(ccnl_total, stocks_to_watch)

    print(f"Starting websocket subscription for: {stocks_to_watch}")
    print(f"Logs are being recorded to: {log_file}")

    ws_thread = threading.Thread(target=ws.start, args=(on_result,), daemon=True)
    ws_thread.start()

    menu()
