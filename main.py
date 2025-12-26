import logging
import os
import re
from datetime import datetime
import pandas as pd
import kis_api.kis_auth as ka
import msvcrt
import threading
import sys
import shutil

# Import refactored modules
import trading_config
import trading_state
import trading_ui
from trading_ui import PrintLevel, print_log, render_ui, show_in_result_area, safe_write, get_fixed_width_name, clear_result_area, input_at, prepare_exit
from account_helper import get_account_balance, get_account_portfolio
from order_handler import handle_place_order, handle_manage_orders

# Specific KIS imports (only asking price subscription uses them?)
from kis_api.domestic_stock.asking_price_total.asking_price_total import asking_price_total
from kis_api.domestic_stock.ccnl_total.ccnl_total import ccnl_total
from kis_api.overseas_stock.asking_price.asking_price import asking_price
from kis_api.overseas_stock.ccnl_notice.ccnl_notice import ccnl_notice
from kis_api.overseas_stock.delayed_ccnl.delayed_ccnl import delayed_ccnl

# [CRITICAL] Configure logging at the VERY TOP
base_dir = os.path.dirname(os.path.abspath(__file__))
latest_log = os.path.join(base_dir, "WebSocket_latest.log")

rotation_msgs = []

# Log Rotation Logic
if os.path.exists(latest_log):
    old_ts = ""
    # 1. Try to extract timestamp from the first few lines of the existing log
    try:
        with open(latest_log, "r", encoding="utf-8-sig") as f:
            for _ in range(20): # Check first 20 lines
                line = f.readline()
                if not line: break
                # Match YYYY-MM-DD HH:MM:SS
                match = re.search(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})", line)
                if match:
                    y, m, d, hh, mm, ss = match.groups()
                    old_ts = f"{y[2:]}_{m}_{d}_{hh}_{mm}_{ss}"
                    break
    except Exception as e:
        rotation_msgs.append(f"[LogRotation] Warning: Could not read timestamp from content: {e}")

    # 2. Fallback to file modification time if no timestamp found in content
    if not old_ts:
        try:
            mtime = os.path.getmtime(latest_log)
            old_ts = datetime.fromtimestamp(mtime).strftime("%y_%m_%d_%H_%M_%S")
        except:
            old_ts = datetime.now().strftime("%y_%m_%d_%H_%M_%S")

    # 3. Define archive name and handle collisions
    archive_name = os.path.join(base_dir, f"WebSocket_{old_ts}.log")
    if os.path.exists(archive_name):
        archive_name = archive_name.replace(".log", f"_{int(datetime.now().timestamp())}.log")

    # 4. Attempt to rotate
    try:
        os.rename(latest_log, archive_name)
        rotation_msgs.append(f"[LogRotation] Archived old log: {os.path.basename(latest_log)} -> {os.path.basename(archive_name)}")
    except PermissionError:
        rotation_msgs.append(f"[LogRotation] Warning: {os.path.basename(latest_log)} is locked. Appending to existing file.")
    except Exception as e:
        rotation_msgs.append(f"[LogRotation] Error during rename: {e}")
else:
    rotation_msgs.append(f"[LogRotation] Fresh session. No existing log file found.")

log_file = latest_log
trading_ui.log_file_path = log_file

# Force reset root logger handlers to prevent leakage
root_logger = logging.getLogger()
if root_logger.handlers:
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

# Initialize logger with both File and temporarily a Stream handler
file_handler = logging.FileHandler(log_file, encoding='utf-8')
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)

# Flush captured rotation messages to both destinations
for msg in rotation_msgs:
    logging.info(msg)

# Remove StreamHandler before Terminal UI starts to prevent layout corruption
root_logger.removeHandler(stream_handler)
logging.info(f"[System] Logging initialized. All system messages now directed to: {os.path.basename(log_file)}")

# Rename local PrintLevel to avoid some typing conflicts if any
PyPrintLevel = PrintLevel

def write_cleared(text, end="\n"):
    """Write text while clearing the current line"""
    safe_write(f"{trading_ui.CLEAR_LINE}{text}{end}")

def on_result(ws, tr_id, df: pd.DataFrame, dm: dict):
    """
    Callback function when data is received.
    """
    if df.empty:
        print_log(PrintLevel.ERROR, f"System Message received for TR: {tr_id}")
        return

    tr_id = tr_id.strip()
    # Process all records in the DataFrame (KIS can send multiple updates in one message)
    for i in range(len(df)):
        row = df.iloc[i]

        if tr_id in ["H0UNASP0", "H0UNCNT0"]: # Market Data
            code = row['MKSC_SHRN_ISCD']

            # Initialize state for code if not exists with all market fields
            if code not in trading_state.stock_data_state:
                trading_state.stock_data_state[code] = {
                    'price': 0, 'ask': 0, 'bid': 0,
                    'change': 0, 'rate': 0.0, 'vol': 0,
                    'time': '000000'
                }

            state = trading_state.stock_data_state[code]
            level = PrintLevel.DEBUG # Default level

            if tr_id == "H0UNASP0": # Stock Asking Price
                state['time'] = row['BSOP_HOUR']
                try:
                    new_ask = int(float(row['ASKP1']))
                    new_bid = int(float(row['BID_PRC1'] if 'BID_PRC1' in row else row['BIDP1']))

                    # Skip if neither ask nor bid changed
                    if state['ask'] == new_ask and state['bid'] == new_bid:
                        continue

                    # Set to DEBUG (Gray)
                    level = PrintLevel.DEBUG

                    state['ask'] = new_ask
                    state['bid'] = new_bid
                except (ValueError, TypeError, KeyError):
                    continue

            elif tr_id == "H0UNCNT0": # Stock Execution
                state['time'] = row['STCK_CNTG_HOUR']
                try:
                    new_price = int(float(row['STCK_PRPR']))
                    new_vol   = int(float(row['CNTG_VOL']))

                    # Execution is INFO level (Colors)
                    level = PrintLevel.INFO

                    state['price']  = new_price
                    state['change'] = int(float(row['PRDY_VRSS']))
                    state['rate']   = float(row['PRDY_CTRT'])
                    state['vol']    = new_vol

                    # Add sign to change for display
                    sign = row['PRDY_VRSS_SIGN']
                    state['sign_str'] = "+" if sign in ['1', '2'] else "-" if sign in ['4', '5'] else " "
                except (ValueError, TypeError, KeyError):
                    continue

            # Format values for the unified log
            time_v = str(state.get('time', '000000')).strip()
            if len(time_v) == 6:
                time_s = f"{time_v[:2]}:{time_v[2:4]}:{time_v[4:6]}"
            else:
                # Handle cases where time might be HHMM or HHMMSS.ms or just a number
                time_s = time_v[-6:] if len(time_v) > 6 else time_v.zfill(6)
                time_s = f"{time_s[:2]}:{time_s[2:4]}:{time_s[4:6]}"

            # Use fallback values if data hasn't arrived yet
            bid_s   = format(state.get('bid', 0), ",")
            ask_s   = format(state.get('ask', 0), ",")
            price_v = state.get('price', 0)
            price_s = format(price_v, ",") if price_v > 0 else "-------"
            vol_s   = format(state.get('vol', 0), ",")
            diff_s  = f"{state.get('sign_str', '')}{format(state.get('change', 0), ',')}"

            # [12:03:44] [MKT][SK하이닉스]
            cfg = trading_config.get_stock_info(code)
            if not cfg:
                # If we can't identify the stock (e.g., due to parsing shift or unknown code), skip it.
                # This prevents trash data like '1' or '189.85' from cluttering the UI.
                continue

            name = cfg.get("name", "Unknown")
            fixed_name = get_fixed_width_name(name, 10)
            msg = (f"[{time_s}] [MKT][{fixed_name}] {code:<6} | "
                   f"Bid: {bid_s:>9} | "
                   f"Last: {price_s:>9} ({vol_s:>6}) | "
                   f"Diff: {diff_s:>9} ({state.get('rate', 0.0):>5.2f}%) | "
                   f"Ask: {ask_s:>9}")

            print_log(level, msg)
            continue

        elif tr_id in ["HDFSASP0", "HDFSCNT0"]: # Overseas Market Data
            # Note: Field names differ from domestic TRs
            code = row.get('symb', row.get('SYMB'))
            if not code: continue



            if code not in trading_state.stock_data_state:
                trading_state.stock_data_state[code] = {
                    'price': 0, 'ask': 0, 'bid': 0,
                    'change': 0, 'rate': 0.0, 'vol': 0,
                    'time': '000000'
                }

            state = trading_state.stock_data_state[code]
            level = PrintLevel.DEBUG

            if tr_id == "HDFSASP0": # Overseas Asking Price
                state['time'] = row.get('xhms', '000000')
                try:
                    # Overseas prices can be floating point
                    state['ask'] = float(row['pask1'])
                    state['bid'] = float(row['pbid1'])
                    level = PrintLevel.DEBUG
                except: continue

            elif tr_id == "HDFSCNT0": # Overseas Execution
                state['time'] = row.get('XHMS', '000000')
                try:
                    state['price']  = float(row['LAST'])
                    state['change'] = float(row['DIFF'])
                    state['rate']   = float(row['RATE'])
                    state['vol']    = float(row['EVOL'])

                    # Update bid/ask from execution record if available
                    if 'PBID' in row: state['bid'] = float(row['PBID'])
                    if 'PASK' in row: state['ask'] = float(row['PASK'])

                    sign = row.get('SIGN', '3')
                    state['sign_str'] = "+" if sign in ['1', '2'] else "-" if sign in ['4', '5'] else " "
                    level = PrintLevel.INFO
                except: continue

            # Format and Log (Shared logic with Domestic)
            time_v = str(state.get('time', '000000')).strip()
            if len(time_v) == 6:
                time_s = f"{time_v[:2]}:{time_v[2:4]}:{time_v[4:6]}"
            else:
                time_s = time_v.zfill(6)
                time_s = f"{time_s[:2]}:{time_s[2:4]}:{time_s[4:6]}"

            # Overseas Bid/Ask often use float
            bid_s   = format(state.get('bid', 0.0), ",.2f") if state.get('bid', 0) > 0 else "0"
            ask_s   = format(state.get('ask', 0.0), ",.2f") if state.get('ask', 0) > 0 else "0"
            price_v = state.get('price', 0.0)
            price_s = format(price_v, ",.2f") if price_v > 0 else "-------"
            vol_v   = state.get('vol', 0.0)
            vol_s   = format(vol_v, ",.0f") if vol_v > 0 else "0"
            diff_s  = f"{state.get('sign_str', '')}{format(state.get('change', 0.0), ',.2f')}"

            cfg = trading_config.get_stock_info(code)
            if not cfg:
                # Skip overseas system messages or misparsed records
                continue

            name = cfg.get("name", "Unknown")
            fixed_name = get_fixed_width_name(name, 10)
            msg = (f"[{time_s}] [MKT][{fixed_name}] {code:<8} | "
                   f"Bid: {bid_s:>9} | "
                   f"Last: {price_s:>9} ({vol_s:>6}) | "
                   f"Diff: {diff_s:>9} ({state.get('rate', 0.0):>5.2f}%) | "
                   f"Ask: {ask_s:>9}")
            print_log(level, msg)
            continue

        elif tr_id == "H0STCNI0": # Domestic Order Notification (Real Only)
            try:
                code = row['STCK_SHRN_ISCD']
                time_v = row['STCK_CNTG_HOUR']
                time_s = f"{time_v[:2]}:{time_v[2:4]}:{time_v[4:6]}"

                # [DUMP] Full row data for debugging
                logging.info(f"--- H0STCNI0 FULL DUMP ---\n{row.to_dict()}")

                cntg_yn = row['CNTG_YN'] # 1: Acceptance, 2: Execution
                rctf_cls = row['RCTF_CLS'] # 01: Order, 02: Cor, 03: Can (Correction 01 or 1?)
                rfus_yn = row.get('RFUS_YN', '0') # Refusal YN (Y/N or 1/0)

                # SELN_BYOV_CLS: 01: Sell, 02: Buy
                side = "BUY" if row['SELN_BYOV_CLS'] == '02' else "SEL"
                order_no = row['ODER_NO']

                cfg = trading_config.get_stock_info(code)

                def safe_int_format(val):
                    try:
                        if not val or str(val).strip() == "": return "0"
                        return format(int(float(val)), ",")
                    except:
                        return "0"

                # Price: Strictly use CNTG_UNPR as requested
                p_cntg = str(row.get('CNTG_UNPR', '0')).strip()
                price = safe_int_format(p_cntg)
                qty = safe_int_format(row['CNTG_QTY'])

                msg_level = PrintLevel.INFO
                extra_info = ""

                if rfus_yn in ['Y', '1']:
                    order_val = "REJ"
                    msg_level = PrintLevel.ERROR
                    # Try to find rejection reason
                    remark = str(row.get('RM', '')).strip()
                    if remark: extra_info = f" ({remark})"
                elif cntg_yn == '2': # EXECUTION
                    order_val = "EXE"
                else: # ORDER / CANCELLATION (Following raw API codes)
                    if rctf_cls in ['0', '00']:
                        order_val = "ODR"
                    elif rctf_cls in ['1', '01']: # Correction
                        order_val = "COR"
                    elif rctf_cls in ['2', '02']: # Cancellation
                        order_val = "CAN"
                    else:
                        order_val = "OTH"

                # Try to get name from config, otherwise use the name in the row
                name = cfg.get("name", row.get('CNTG_ISNM40', 'Unknown')).strip()
                fixed_name = get_fixed_width_name(name, 10)

                # PREMIUM COMPACT LOG FORMAT
                msg = (f"[{time_s}] [{side}][{order_val}] [{fixed_name}] {code:<6} | "
                       f"Qty: {qty:>6} | Prc: {price:>9} | No: {order_no}{extra_info}")

                print_log(msg_level, msg)
                continue
            except Exception as e:
                print_log(PrintLevel.ERROR, f"Error parsing H0STCNI0: {e}")
                continue

        elif tr_id in ["H0GSCNI0", "H0GSCNI9"]: # Overseas Order Notification
            try:
                # Based on observed KIS raw data for Overseas Notifications
                # Note: Field alignment is handled by kis_auth's prepending logic.

                # Debug: Log raw row content to DEBUG only
                if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
                    raw_list = row.tolist() if hasattr(row, 'tolist') else list(row)
                    logging.debug(f"[{tr_id} RAW] {raw_list}")

                code = str(row.get('STCK_SHRN_ISCD', 'Unknown')).strip()
                # If ticker is malformed (too many zeros), try to clean it
                if code.startswith('000') and len(code) > 8:
                    code = code.lstrip('0') or "Unknown"

                cfg = trading_config.get_stock_info(code)
                time_v = str(row.get('STCK_CNTG_HOUR', '000000')).strip()

                # Use current market time if available, otherwise calculate relative to system clock
                if not time_v or time_v in ["0", "000000"]:
                    # If US market, adjust to US Eastern Time (approx -14h from KST in winter)
                    if cfg and cfg.get('market') in ['NASDAQ', 'NYSE', 'AMEX']:
                        from datetime import timedelta
                        time_s = (datetime.now() - timedelta(hours=14)).strftime("%H:%M:%S")
                    else:
                        time_s = datetime.now().strftime("%H:%M:%S")
                else:
                    if len(time_v) >= 6:
                        time_s = f"{time_v[:2]}:{time_v[2:4]}:{time_v[4:6]}"
                    else:
                        time_s = time_v.zfill(6)
                        time_s = f"{time_s[:2]}:{time_s[2:4]}:{time_s[4:6]}"

                cntg_yn = str(row.get('CNTG_YN', '1')).strip()
                rctf_cls = str(row.get('RCTF_CLS', '01')).strip()
                rfus_yn = str(row.get('RFUS_YN', 'N')).strip()
                side = "BUY" if str(row.get('SELN_BYOV_CLS')) == '02' else "SEL"
                order_no = str(row.get('ODER_NO', '0'))



                def get_val(key, default=0):
                    v = row.get(key, default)
                    try: return float(v)
                    except: return 0

                # OVERSEAS PRICE SCALING: KIS uses integers with 4 decimal places implied
                price_v = get_val('CNTG_UNPR')
                if price_v >= 10000: price_v = price_v / 10000.0

                qty_v = get_val('CNTG_QTY')
                if qty_v > 1000000: qty_v = get_val('ODER_QTY')

                price = format(price_v, ",.2f")
                qty = format(qty_v, ",.0f")

                msg_level = PrintLevel.INFO
                extra_info = ""

                # Refusal check
                if rfus_yn in ['Y', '1']:
                    order_val = "REJ"
                    msg_level = PrintLevel.ERROR
                elif cntg_yn == '2':
                    order_val = "EXE"
                else:
                    if rctf_cls in ['0', '00']: order_val = "ODR"
                    elif rctf_cls in ['1', '01']: order_val = "COR" # Correction
                    elif rctf_cls in ['2', '02']: order_val = "CAN" # Cancellation
                    else: order_val = "OTH"

                name = cfg.get("name", row.get('CNTG_ISNM', 'Unknown')).strip()
                fixed_name = get_fixed_width_name(name, 10)

                msg = (f"[{time_s}] [{side}][{order_val}] [{fixed_name}] {code:<8} | "
                       f"Qty: {qty:>6} | Prc: {price:>9} | No: {order_no}{extra_info}")

                print_log(msg_level, msg)
                continue
            except Exception as e:
                print_log(PrintLevel.ERROR, f"Error parsing overseas notification: {e}")
                continue

        else:
            if i == 0: # Only once per batch
                print_log(PrintLevel.DEBUG, f"Unhandled TR_ID: {tr_id}")

def inquire_combined_cash() -> list:
    """
    Inquire both Domestic (KRW) and Overseas (USD) Cash Info
    """
    lines = [
        "=" * 40,
        " [Account Cash Information]",
        "=" * 40,
    ]

    bal = get_account_balance()

    if bal['error_krw']:
        lines.append(f" KRW Error       : {bal['error_krw']}")
    else:
        lines.append(f" KRW Deposit     : {format(bal['krw_deposit'], ','):>12} KRW")
        lines.append(f" Orderable KRW   : {format(bal['krw_orderable'], ','):>12} KRW")

    lines.append("-" * 40)

    if bal['error_usd']:
        lines.append(f" USD Error       : {bal['error_usd']}")
    else:
        lines.append(f" USD Deposit     : {format(bal['usd_deposit'], ',.2f'):>12} USD")
        lines.append(f" Withdrawable USD: {format(bal['usd_withdrawable'], ',.2f'):>12} USD")


    lines.append("-" * 40)
    lines.append(f" (Log: {os.path.basename(log_file)})")
    lines.append(" [Press any key to return to menu]")

    return lines

def inquire_portfolio() -> list:
    """
    Inquire Portfolio (Holdings)
    """
    clear_result_area()
    lines = ["=" * 60, " [Account Portfolio]", "=" * 60, "Fetching data..."]
    show_in_result_area(lines)

    port = get_account_portfolio()

    lines = ["=" * 60, " [Account Portfolio]", "=" * 60]

    # Domestic
    lines.append(" [Domestic Stocks]")
    if port.get('dom_error'):
        lines.append(f"  [ERROR] {port['dom_error']}")
    elif not port['domestic']:
        lines.append("  (No holdings)")
    else:
        # Header
        lines.append(f"  {'Name':<14} | {'Qty':>6} | {'AvgPrice':>10} | {'CurPrice':>10} | {'P/L(%)':>10}")
        lines.append("-" * 71)
        for item in port['domestic']:
            name = get_fixed_width_name(item['name'], 14)
            lines.append(f"  {name} | {item['qty']:>6,} | {item['avg_price']:>10,.0f} | {item['cur_price']:>10,.0f} | {item['pnl_rate']:>9.2f}%")

        # Summary
        total = port.get('dom_total', {})
        if total:
            try:
                tot_evlu = float(total.get('tot_evlu_amt', 0))
                pnl_amt = float(total.get('evlu_pfls_amt_tot', 0))
                lines.append("-" * 71)
                lines.append(f"  Total Eval: {tot_evlu:>12,.0f} | Total P/L: {pnl_amt:>12,.0f}")
            except: pass

    lines.append("-" * 60)

    # Overseas
    lines.append(" [Overseas Stocks]")
    if port.get('ovs_error') and not port['overseas']:
        lines.append(f"  [ERROR] {port['ovs_error']}")
    elif not port['overseas']:
        lines.append("  (No holdings)")
    else:
        # Header
        lines.append(f"  {'Name':<14} | {'Qty':>6} | {'AvgPrice':>10} | {'CurPrice':>10} | {'P/L(%)':>8}")
        lines.append("-" * 60)
        for item in port['overseas']:
            name = get_fixed_width_name(item['name'], 14)
            ex_code = item.get('exchange', 'US')
            # Show exchange code if not just generic? Or just format nice
            # E.g. "[NASD] Apple" or just append to name?
            # Space is limited. Let's just assume list is mixed.
            # Maybe: Name......... (NASD)
            # Or just rely on code/name.
            lines.append(f"  {name} | {item['qty']:>6,.2f} | ${item['avg_price']:>9.2f} | ${item['cur_price']:>9.2f} | {item['pnl_rate']:>7.2f}%")

    lines.append("-" * 60)
    lines.append(" [Press any key to return to menu]")

    return lines

def menu():
    # To modify global print_log_level from trading_ui, we access it directly or via helper.
    # But print_log_level is module-level in trading_ui.
    # "global print_log_level" in main.py is referring to main's variable, but we deleted it.
    # We should use trading_ui.print_log_level.

    os.system('cls' if os.name == 'nt' else 'clear')
    render_ui(full_refresh=True)

    while True:
        render_ui(full_refresh=True)
        choice = input_at(10, 2, "Enter Choice: ").strip()

        if choice == '1':
            clear_result_area()
            lines = inquire_combined_cash()
            show_in_result_area(lines)
            msvcrt.getch()
        elif choice == '2':
            handle_place_order()
        elif choice == '3':
            handle_manage_orders()
        elif choice == '4':
            lines = inquire_portfolio()
            show_in_result_area(lines)
            msvcrt.getch()
        elif choice == '0':
            # Toggle Log Level: INFO -> DEBUG -> ERROR -> INFO ...
            if trading_ui.print_log_level == PrintLevel.INFO:
                trading_ui.print_log_level = PrintLevel.DEBUG
            elif trading_ui.print_log_level == PrintLevel.DEBUG:
                trading_ui.print_log_level = PrintLevel.ERROR
            else:
                trading_ui.print_log_level = PrintLevel.INFO
            print_log(PrintLevel.ERROR, f"Log Level Changed to: {trading_ui.print_log_level.name}")
        elif choice.lower() == 'c':
            trading_ui.clear_order_logs()
        elif choice.lower() == 'q':
            prepare_exit()
            print("Exiting...")
            os._exit(0)
        else:
            pass

if __name__ == "__main__":
    print("=== KIS Real-time Trading System ===")

    ka.auth()
    ka.auth_ws()

    ws = ka.KISWebSocket(api_url="")

    # Load stocks to watch from config, filtering out disabled ones
    watch_list_kr = [s["ticker"] for s in trading_config.CONFIG.get("KR", []) if not s.get("disabled", False)]
    watch_list_us = [s["ticker"] for s in trading_config.CONFIG.get("US", []) if not s.get("disabled", False)]

    # Personal Fill Notifications (Order/Execution Notifications)
    # These TR IDs (H0STCNI0 for Domestic, H0GSCNI0 for Overseas) use HTSID as the key, not tickers.
    # They should be subscribed ONLY ONCE.
    htsid = ka.getTREnv().my_htsid
    if htsid:
        # Domestic Notification
        # (Importing ccnl_total as request function for consistency if it handles H0STCNI0)
        # Actually H0STCNI0 is for domestic order alerts.
        # For now we use standard tickers for market data and HTSID for personal alerts.
        ws.subscribe(ccnl_notice, htsid, kwargs={"env_dv": "real"})

    if watch_list_kr:
        ws.subscribe(asking_price_total, watch_list_kr)
        ws.subscribe(ccnl_total, watch_list_kr)

    if watch_list_us:
        # KIS Overseas Real-time TRs require prefixes like DNAS (NASDAQ) or DNYS (NYSE) or DAMS (AMEX).
        formatted_us_list = []
        for ticker in watch_list_us:
            if any(ticker.startswith(p) for p in ["DNAS", "DNYS", "DAMS"]):
                formatted_us_list.append(ticker)
                continue

            info = trading_config.get_stock_info(ticker)
            market = info.get("market", "").upper()

            if market == "NASDAQ":
                formatted_us_list.append(f"DNAS{ticker}")
            elif market == "NYSE":
                formatted_us_list.append(f"DNYS{ticker}")
            elif market == "AMEX":
                formatted_us_list.append(f"DAMS{ticker}")
            else:
                # Default fallback
                formatted_us_list.append(f"DNAS{ticker}")

        # Use the formatted list for subscription
        ws.subscribe(asking_price, formatted_us_list)
        ws.subscribe(delayed_ccnl, formatted_us_list)

    # Register callback (Try add_callback as generic guess)
    if hasattr(ws, 'add_callback'):
        ws.add_callback(on_result)
    elif hasattr(ws, 'on'):
        ws.on("message", on_result)
    else:
        # Fallback: Assume library uses global handler or set property
        # print_log(PrintLevel.INFO, "Could not set callback explicitly. Assuming library handles it.")
        # Try setting attribute directly if simple implementation
        ws.callback = on_result

    # Start WebSocket thread
    ws_thread = threading.Thread(target=ws.start, args=(on_result,), daemon=True)
    ws_thread.start()

    menu()
