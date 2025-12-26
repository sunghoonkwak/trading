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

# UI Configuration
LOG_BUFFER_SIZE = 30
log_buffer = deque(maxlen=LOG_BUFFER_SIZE)
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
    if level <= print_log_level:
        colored_log = log
        if level == PrintLevel.ERROR:
            colored_log = f"\033[91m{log}\033[0m" # Red
        elif level == PrintLevel.INFO:
            colored_log = f"\033[93m{log}\033[0m" # Yellow

        # Add to buffer
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
                " 1. Get Cash Info",
                " 0. Change Log Level",
                " q. Exit",
                "-" * min(cols, 40),
                "Enter Choice: "
            ]
            for line in menu_lines:
                sys.stdout.write(f"{CLEAR_LINE}{line}\n")

        # 2. Jump to Log Area (Line 11)
        sys.stdout.write(MOVE_TO_LOG_START)
        sys.stdout.write("\n" + "=" * (cols - 1) + "\n")
        sys.stdout.write(f"{CLEAR_LINE} Recent Logs (Max visible: {visible_logs_count}):\n")
        sys.stdout.write("-" * (cols - 1) + "\n")

        # Print top N logs from buffer that fit the screen
        current_logs = list(log_buffer)[:visible_logs_count]
        for log in current_logs:
            sys.stdout.write(f"{CLEAR_LINE}{log[:cols+20]}\n")

        # Clear remaining rows below logs up to terminal bottom to prevent ghosting
        for _ in range(max(0, rows - 15 - len(current_logs))):
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

    # Extract common data
    code = df['MKSC_SHRN_ISCD'].iloc[0]

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
        state['time'] = df['BSOP_HOUR'].iloc[0]
        try:
            new_ask = int(float(df['ASKP1'].iloc[0]))
            new_bid = int(float(df['BIDP1'].iloc[0]))

            # Skip if neither ask nor bid changed
            if state['ask'] == new_ask and state['bid'] == new_bid:
                return
            else:
                level = PrintLevel.INFO

            state['ask'] = new_ask
            state['bid'] = new_bid
        except (ValueError, TypeError):
            return

    elif tr_id == "H0UNCNT0": # Stock Execution
        state['time'] = df['STCK_CNTG_HOUR'].iloc[0]
        try:
            new_price = int(float(df['STCK_PRPR'].iloc[0]))
            new_vol   = int(float(df['CNTG_VOL'].iloc[0]))

            # Check for INFO level conditions: price change or large volume
            if state['price'] != new_price or new_vol >= 100:
                level = PrintLevel.INFO

            state['price']  = new_price
            state['change'] = int(float(df['PRDY_VRSS'].iloc[0]))
            state['rate']   = float(df['PRDY_CTRT'].iloc[0])
            state['vol']    = new_vol

            # Add sign to change for display
            # 1: Upper limit, 2: Up, 3: Flat, 4: Lower limit, 5: Down
            sign = df['PRDY_VRSS_SIGN'].iloc[0]
            state['sign_str'] = "+" if sign in ['1', '2'] else "-" if sign in ['4', '5'] else " "
        except (ValueError, TypeError):
            return

    # Skip if we don't have enough data yet
    if state['price'] == 0:
        return

    # Format values for the unified log
    time_s  = f"{state['time'][:2]}:{state['time'][2:4]}:{state['time'][4:6]}"
    bid_s   = format(state['bid'], ",")
    ask_s   = format(state['ask'], ",")
    price_s = format(state['price'], ",")
    vol_s   = format(state['vol'], ",")
    diff_s  = f"{state.get('sign_str', '')}{format(state['change'], ',')}"

    # Unified Market Log Format
    # [Market] [10:12:38] 005930 | Bid:   114,800 | Last:   114,850 (  100) | Diff:   +3,750 ( 3.38%) | Ask:   114,900
    msg = (f"[Market] [{time_s}] {code:<6} | "
           f"Bid: {bid_s:>9} | "
           f"Last: {price_s:>9} ({vol_s:>6}) | "
           f"Diff: {diff_s:>9} ({state['rate']:>5.2f}%) | "
           f"Ask: {ask_s:>9}")

    print_log(level, msg)

def get_account_info_domastic() -> list:
    """
    Get domestic stock account info lines for display
    """
    today = datetime.today().strftime("%Y%m%d")

    params = {
        "CANO": ka.getTREnv().my_acct,
        "ACNT_PRDT_CD": ka.getTREnv().my_prod,
        "INQR_DVSN_CD": "01",
        "IVRE_DVSN": "01",
        "BASS_DT": today,
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRTS_DVSN": "01",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
        "WCRC_FRCR_DVSN_CD": "01"
    }

    url = "/uapi/domestic-stock/v1/trading/inquire-account-balance"
    res = ka._url_fetch(url, "CTRP6010R", "N", params)

    if res.isOK():
        body = res.getBody()
        output = getattr(body, 'output1', None) or getattr(body, 'output2', None) or getattr(body, 'output3', None)

        if output:
            total_cash = output.get('dnca_tot_amt') or output.get('tot_dncl_amt', '0')
            available  = output.get('ord_psbl_cash') or output.get('tot_dncl_amt', '0')
            total_asst = output.get('tot_asst_amt2') or output.get('tot_evlu_amt', '0')

            def safe_format_krw(val):
                try:
                    return format(int(float(val)), ",")
                except (ValueError, TypeError):
                    return val

            lines = [
                "=" * 40,
                " [Account Info]",
                "=" * 40,
                f" Total Deposit : {safe_format_krw(total_cash):>12} KRW",
                f" Available     : {safe_format_krw(available):>12} KRW",
                f" Total Assets  : {safe_format_krw(total_asst):>12} KRW",
                "-" * 40,
                " (Press Enter to return to menu)",
            ]
            return lines
        else:
            return ["Error: No account data found."]
    else:
        return [f"Error: {res.getRTName()}"]

def menu():
    global print_log_level
    os.system('cls' if os.name == 'nt' else 'clear')
    render_ui(full_refresh=True)

    while True:
        render_ui(full_refresh=True)
        safe_write("\033[8;15H")

        choice = input()

        if choice == '1':
            lines = get_account_info_domastic()
            with terminal_lock:
                sys.stdout.write(SAVE_CURSOR)
                sys.stdout.write(HOME)
                for line in lines:
                    sys.stdout.write(f"{CLEAR_LINE}{line}\n")
                for _ in range(max(0, 10 - len(lines))):
                    sys.stdout.write(f"{CLEAR_LINE}\n")
                sys.stdout.write(RESTORE_CURSOR)
                sys.stdout.flush()
            input()
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

    ws = ka.KISWebSocket(api_url="/tryitout")

    stocks_to_watch = ['005930', '000660']
    ws.subscribe(asking_price_total, stocks_to_watch)
    ws.subscribe(ccnl_total, stocks_to_watch)

    print(f"Starting websocket subscription for: {stocks_to_watch}")
    print(f"Logs are being recorded to: {log_file}")

    ws_thread = threading.Thread(target=ws.start, args=(on_result,), daemon=True)
    ws_thread.start()

    menu()
