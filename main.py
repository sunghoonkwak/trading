import logging
import pandas as pd
from key.key import get_key_secret_from_password
import kis_auth as ka

# Configure logging
logging.basicConfig(level=logging.INFO)

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

if __name__ == "__main__":
    print("=== KIS Real-time Trading System ===")

    ka.auth_ws()
        
    # 1. Initialize WebSocket
    # For production: "/tryitout" or correct path
    # In KIS, the real-time path is usually "/tryitout" for testing or specific for real
    ws = ka.KISWebSocket(api_url="/tryitout") # Path based on KIS manual
        
    # 2. Subscribe to stocks
    stocks_to_watch = ['005930', '000660'] # Samsung, SK Hynix
    ws.subscribe(stock_price_request, stocks_to_watch)
        
    print(f"Starting websocket subscription for: {stocks_to_watch}")
        
    # 3. Start the websocket client
    ws.start(on_result)
