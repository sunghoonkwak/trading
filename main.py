import logging
import pandas as pd
import kis_auth as ka
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

def stock_price_request(tr_type, data, **kwargs):
    """
    Builds the websocket message for real-time stock price (H0STCNT0).
    """
    tr_id = "H0STCNT0" # Real-time domestic stock contract

    msg = {
        "header": {
            "approval_key": ka._base_headers_ws["approval_key"],
            "custtype": "P",
            "tr_type": tr_type,
            "content-type": "utf-8"
        },
        "body": {
            "input": {
                "tr_id": tr_id,
                "tr_key": data
            }
        }
    }

    # Column headers for H0STCNT0
    columns = [
        'MKSC_SHRN_ISCD', 'TICK_HOUR', 'STCK_PRPR', 'PRDY_VRSS_SIGN', 'PRDY_VRSS',
        'PRDY_CTRT', 'WGHN_AVRG_STCK_PRC', 'STCK_OPRC', 'STCK_HGPR', 'STCK_LWPR',
        'ASKP1', 'BIDP1', 'CNTG_VOL', 'ACML_VOL', 'ACML_TR_PBMN', 'SELN_CNTG_CSNU',
        'SHNU_CNTG_CSNU', 'NTBY_CNTG_CSNU', 'CTTR', 'SELN_CNTG_SMTN', 'SHNU_CNTG_SMTN',
        'CCLD_DVSN', 'SHNU_RATE', 'PRDY_VOL_VRSS_ACML_VOL_RATE', 'OPRC_HOUR',
        'OPRC_VRSS_PRPR_SIGN', 'OPRC_VRSS_PRPR', 'HGPR_HOUR', 'HGPR_VRSS_PRPR_SIGN',
        'HGPR_VRSS_PRPR', 'LWPR_HOUR', 'LWPR_VRSS_PRPR_SIGN', 'LWPR_VRSS_PRPR',
        'BSOP_DATE', 'NEW_MKOP_CLS_CODE', 'TRHT_YN', 'ASKP_RSQN1', 'BIDP_RSQN1',
        'TOTAL_ASKP_RSQN', 'TOTAL_BIDP_RSQN', 'VOL_TNRT', 'PRDY_SMNS_HOUR_ACML_VOL',
        'PRDY_SMNS_HOUR_ACML_VOL_RATE', 'HOUR_CLS_CODE', 'MRKT_TRTM_CLS_CODE', 'VI_STND_PRC'
    ]

    return msg, columns

def on_result(ws, tr_id, df: pd.DataFrame, dm: dict):
    """
    Callback function when data is received.
    """
    if not df.empty:
        # Extract meaningful data
        code = df['MKSC_SHRN_ISCD'].iloc[0]
        price = df['STCK_PRPR'].iloc[0]
        time = df['TICK_HOUR'].iloc[0]
        change = df['PRDY_VRSS'].iloc[0]

        print(f"[{time}] Code: {code}, Current Price: {price}, Change: {change}")
    else:
        print(f"System Message received for TR: {tr_id}")

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
    while True:
        print("\n=== Menu ===")
        print("1. get cash info")
        print("0. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            get_account_info_domastic()
        elif choice == '0':
            print("Exiting...")
            os._exit(0) # Abrupt exit to stop background thread as well
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    print("=== KIS Real-time Trading System ===")

    ka.auth()
    ka.auth_ws()

    # 1. Initialize WebSocket
    ws = ka.KISWebSocket(api_url="/tryitout")

    # 2. Subscribe to stocks
    stocks_to_watch = ['005930', '000660']
    ws.subscribe(stock_price_request, stocks_to_watch)

    print(f"Starting websocket subscription for: {stocks_to_watch}")
    print(f"Logs are being recorded to: {log_file}")

    # 3. Start the websocket client in a background thread
    ws_thread = threading.Thread(target=ws.start, args=(on_result,), daemon=True)
    ws_thread.start()

    # 4. menu for sending cmd in main thread
    menu()
