import logging
import pandas as pd
import kis_api.kis_auth as ka
import threading
import os
from datetime import datetime

# Configure logging with dynamic filename based on server start time
log_timestamp = datetime.now().strftime("%y_%m_%d_%H_%M_%S")
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"WebSocket_{log_timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        # logging.StreamHandler() # Uncomment to see logs in console too
    ]
)

# Global flag for toggling real-time data printing
class PrintLevel:
    ERROR = 0
    INFO = 1
    DEBUG = 2
    MAX = 3

print_log_level = PrintLevel.INFO

# Data structure to store the last state for each code
stock_data_state = {} # { 'code': { 'price': val, 'ask': val, 'bid': val } }

# Logging functions
def print_log(level, log):
    if level <= print_log_level:
        if level == PrintLevel.ERROR:
            print(f"\033[91m{log}\033[0m") # Red for error
        elif level == PrintLevel.INFO:
            print(f"\033[93m{log}\033[0m") # Yellow for info
        else:
            print(log)

def on_result(ws, tr_id, df: pd.DataFrame, dm: dict):
    """
    Callback function when data is received.
    """
    if df.empty:
        print_log(PrintLevel.ERROR, f"System Message received for TR: {tr_id}")
        return

    # Extract common data
    code = df['MKSC_SHRN_ISCD'].iloc[0]
    
    # Initialize state for code if not exists
    if code not in stock_data_state:
        stock_data_state[code] = {'price': None, 'ask': None, 'bid': None}

    state = stock_data_state[code]

    if tr_id == "H0UNASP0": # 주식 호가
        time = df['BSOP_HOUR'].iloc[0]
        try:
            ask1 = int(float(df['ASKP1'].iloc[0]))
            bid1 = int(float(df['BIDP1'].iloc[0]))
            total_ask = int(float(df['TOTAL_ASKP_RSQN'].iloc[0]))
            total_bid = int(float(df['TOTAL_BIDP_RSQN'].iloc[0]))
        except (ValueError, TypeError):
            return # Skip if data is invalid

        # Check if changed
        is_changed = (state['ask'] != ask1 or state['bid'] != bid1)
        level = PrintLevel.INFO if is_changed else PrintLevel.DEBUG
        
        # Update state
        state['ask'] = ask1
        state['bid'] = bid1
        
        # Formatted output with safe comma formatting
        ask_s = format(ask1, ",")
        bid_s = format(bid1, ",")
        t_ask_s = format(total_ask, ",")
        t_bid_s = format(total_bid, ",")
        
        msg = f"[OrderBook]  [{time}] Code: {code:<6} | Ask  : {ask_s:>10} | Bid  : {bid_s:>10} | Total: {t_ask_s:>10} / {t_bid_s:<10}"
        print_log(level, msg)

    elif tr_id == "H0UNCNT0": # 주식 체결
        time = df['STCK_CNTG_HOUR'].iloc[0]
        try:
            price  = int(float(df['STCK_PRPR'].iloc[0]))
            change = int(float(df['PRDY_VRSS'].iloc[0]))
            vol    = int(float(df['CNTG_VOL'].iloc[0]))
        except (ValueError, TypeError):
            return # Skip if data is invalid
            
        # Check if changed or large volume (User request: vol >= 100)
        is_changed = (state['price'] != price)
        level = PrintLevel.INFO if (is_changed or vol >= 100) else PrintLevel.DEBUG
        
        # Update state
        state['price'] = price
        
        # Formatted output with safe comma formatting
        price_s = format(price, ",")
        chg_s   = format(change, ",")
        vol_s   = format(vol, ",")
        
        msg = f"[Trade]      [{time}] Code: {code:<6} | Price: {price_s:>10} | Diff : {chg_s:>8} | Vol  : {vol_s:>10}"
        print_log(level, msg)

    else:
        print_log(PrintLevel.ERROR, f"[{tr_id}] Unknown data received for code: {code}")

def get_account_info_domastic() -> dict:
    """
    Get domestic stock account info
    """
    today = datetime.today().strftime("%Y%m%d")

    # Set Parameters
    params = {
        "CANO": ka.getTREnv().my_acct,      # Account number (8 digits)
        "ACNT_PRDT_CD": ka.getTREnv().my_prod, # Account product code (2 digits)
        "INQR_DVSN_CD": "01",              # Inquiry type (01: Default)
        "IVRE_DVSN": "01",                 # Currency type (01: KRW)
        "BASS_DT": today,                  # Standard Date
        "UNPR_DVSN": "01",                 # Unit Price Division (01: Basic)
        "FUND_STTL_ICLD_YN": "N",          # Fund Settlement Included (N: No)
        "FNCG_AMT_AUTO_RDPT_YN": "N",      # Financing Amount Auto Redemption (N: No)
        "PRTS_DVSN": "01",                 # Partial inquiry (01: Total)
        "CTX_AREA_FK100": "",              # Context area FK
        "CTX_AREA_NK100": "",              # Context area NK
        "WCRC_FRCR_DVSN_CD": "01"          # Won/Foreign Currency (01: Won)
    }

    # Fetch Data using _url_fetch
    url = "/uapi/domestic-stock/v1/trading/inquire-account-balance"
    res = ka._url_fetch(url, "CTRP6010R", "N", params)

    if res.isOK():
        body = res.getBody()

        # Determine which output field to use
        output = None
        if hasattr(body, 'output1') and body.output1:
            output = body.output1
        elif hasattr(body, 'output2') and body.output2:
            output = body.output2
        elif hasattr(body, 'output3') and body.output3:
            output = body.output3

        if output:
            total_cash = output.get('dnca_tot_amt') or output.get('tot_dncl_amt', 'N/A')
            available = output.get('ord_psbl_cash') or output.get('tot_dncl_amt', 'N/A')
            withdrawable = output.get('prvs_rcdl_exca_amt') or output.get('tot_dncl_amt', 'N/A')

            print(f"\n[Account Info]")
            print(f"Total KRW Deposit: {total_cash} KRW")
            print(f"Available Cash: {available} KRW")
            print(f"Withdrawable Cash: {withdrawable} KRW")

            if 'tot_asst_amt2' in output:
                print(f"Total Assets: {output['tot_asst_amt2']} KRW")

            return {
                "total": total_cash,
                "available": available,
                "withdrawable": withdrawable
            }
        else:
            print("\n[Warning] No summary data found in response.")
            print("Response Body Structure:", body._asdict())
            return None
    else:
        res.printError(url)
        return None

def menu():
    global print_log_level
    while True:
        print(f"\n=== Menu (Log Level: {print_log_level}) ===")
        print("1. get cash info")
        print("0. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            get_account_info_domastic()
        elif choice == '0':
            print("Exiting...")
            os._exit(0) # Abrupt exit to stop background thread as well
        elif choice == "":
            print_log_level = (print_log_level + 1) % PrintLevel.MAX
            print(f"\n[System] Real-time log level changed to {print_log_level}")
        else:
            print("Invalid choice. Please try again.")

from kis_api.domestic_stock.asking_price_total.asking_price_total import asking_price_total
from kis_api.domestic_stock.ccnl_total.ccnl_total import ccnl_total

if __name__ == "__main__":
    print("=== KIS Real-time Trading System ===")

    # 1. get token and ws token
    ka.auth()
    ka.auth_ws()

    # 2. Initialize WebSocket
    ws = ka.KISWebSocket(api_url="/tryitout")

    # 3. Subscribe to stocks
    stocks_to_watch = ['005930', '000660']
    ws.subscribe(asking_price_total, stocks_to_watch)
    ws.subscribe(ccnl_total, stocks_to_watch)

    print(f"Starting websocket subscription for: {stocks_to_watch}")
    print(f"Logs are being recorded to: {log_file}")

    # 4. Start the websocket client in a background thread
    ws_thread = threading.Thread(target=ws.start, args=(on_result,), daemon=True)
    ws_thread.start()

    # 5. menu for sending cmd in main thread
    menu()
