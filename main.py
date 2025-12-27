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
from account_helper import get_integrated_account_info
from order_handler import handle_place_order, handle_manage_orders

# Specific KIS imports
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
    try:
        with open(latest_log, "r", encoding="utf-8-sig") as f:
            for _ in range(20):
                line = f.readline()
                if not line: break
                match = re.search(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})", line)
                if match:
                    y, m, d, hh, mm, ss = match.groups()
                    old_ts = f"{y[2:]}_{m}_{d}_{hh}_{mm}_{ss}"
                    break
    except Exception as e:
        rotation_msgs.append(f"[LogRotation] Warning: Could not read timestamp from content: {e}")

    if not old_ts:
        try:
            mtime = os.path.getmtime(latest_log)
            old_ts = datetime.fromtimestamp(mtime).strftime("%y_%m_%d_%H_%M_%S")
        except:
            old_ts = datetime.now().strftime("%y_%m_%d_%H_%M_%S")

    archive_name = os.path.join(base_dir, f"WebSocket_{old_ts}.log")
    if os.path.exists(archive_name):
        archive_name = archive_name.replace(".log", f"_{int(datetime.now().timestamp())}.log")

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

# Force reset root logger handlers
root_logger = logging.getLogger()
if root_logger.handlers:
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

file_handler = logging.FileHandler(log_file, encoding='utf-8')
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)

for msg in rotation_msgs:
    logging.info(msg)

root_logger.removeHandler(stream_handler)
logging.info(f"[System] Logging initialized. All system messages now directed to: {os.path.basename(log_file)}")

PyPrintLevel = PrintLevel

def write_cleared(text, end="\n"):
    safe_write(f"{trading_ui.CLEAR_LINE}{text}{end}")

def on_result(ws, tr_id, df: pd.DataFrame, dm: dict):
    if df.empty:
        print_log(PrintLevel.ERROR, f"System Message received for TR: {tr_id}")
        return

    tr_id = tr_id.strip()
    for i in range(len(df)):
        row = df.iloc[i]

        if tr_id in ["H0UNASP0", "H0UNCNT0"]: # Market Data
            code = row['MKSC_SHRN_ISCD']
            if code not in trading_state.stock_data_state:
                trading_state.stock_data_state[code] = {
                    'price': 0, 'ask': 0, 'bid': 0,
                    'change': 0, 'rate': 0.0, 'vol': 0,
                    'time': '000000'
                }

            state = trading_state.stock_data_state[code]
            level = PrintLevel.DEBUG

            if tr_id == "H0UNASP0":
                state['time'] = row['BSOP_HOUR']
                try:
                    new_ask = int(float(row['ASKP1']))
                    new_bid = int(float(row['BID_PRC1'] if 'BID_PRC1' in row else row['BIDP1']))
                    if state['ask'] == new_ask and state['bid'] == new_bid: continue
                    level = PrintLevel.DEBUG
                    state['ask'] = new_ask
                    state['bid'] = new_bid
                except: continue

            elif tr_id == "H0UNCNT0":
                state['time'] = row['STCK_CNTG_HOUR']
                try:
                    new_price = int(float(row['STCK_PRPR']))
                    new_vol   = int(float(row['CNTG_VOL']))
                    level = PrintLevel.INFO
                    state['price']  = new_price
                    state['change'] = int(float(row['PRDY_VRSS']))
                    state['rate']   = float(row['PRDY_CTRT'])
                    state['vol']    = new_vol
                    sign = row['PRDY_VRSS_SIGN']
                    state['sign_str'] = "+" if sign in ['1', '2'] else "-" if sign in ['4', '5'] else " "
                except: continue

            time_v = str(state.get('time', '000000')).strip()
            time_s = f"{time_v[:2]}:{time_v[2:4]}:{time_v[4:6]}" if len(time_v) == 6 else time_v.zfill(6)

            bid_s   = format(state.get('bid', 0), ",")
            ask_s   = format(state.get('ask', 0), ",")
            price_v = state.get('price', 0)
            price_s = format(price_v, ",") if price_v > 0 else "-------"
            vol_s   = format(state.get('vol', 0), ",")
            diff_s  = f"{state.get('sign_str', '')}{format(state.get('change', 0), ',')}"

            cfg = trading_config.get_stock_info(code)
            if not cfg: continue

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

            if tr_id == "HDFSASP0":
                state['time'] = row.get('xhms', '000000')
                try:
                    state['ask'] = float(row['pask1'])
                    state['bid'] = float(row['pbid1'])
                    level = PrintLevel.DEBUG
                except: continue

            elif tr_id == "HDFSCNT0":
                state['time'] = row.get('XHMS', '000000')
                try:
                    state['price']  = float(row['LAST'])
                    state['change'] = float(row['DIFF'])
                    state['rate']   = float(row['RATE'])
                    state['vol']    = float(row['EVOL'])
                    if 'PBID' in row: state['bid'] = float(row['PBID'])
                    if 'PASK' in row: state['ask'] = float(row['PASK'])
                    sign = row.get('SIGN', '3')
                    state['sign_str'] = "+" if sign in ['1', '2'] else "-" if sign in ['4', '5'] else " "
                    level = PrintLevel.INFO
                except: continue

            time_v = str(state.get('time', '000000')).strip()
            time_s = f"{time_v[:2]}:{time_v[2:4]}:{time_v[4:6]}" if len(time_v) >= 6 else time_v.zfill(6)

            bid_s   = format(state.get('bid', 0.0), ",.2f") if state.get('bid', 0) > 0 else "0"
            ask_s   = format(state.get('ask', 0.0), ",.2f") if state.get('ask', 0) > 0 else "0"
            price_v = state.get('price', 0.0)
            price_s = format(price_v, ",.2f") if price_v > 0 else "-------"
            vol_v   = state.get('vol', 0.0)
            vol_s   = format(vol_v, ",.0f") if vol_v > 0 else "0"
            diff_s  = f"{state.get('sign_str', '')}{format(state.get('change', 0.0), ',.2f')}"

            cfg = trading_config.get_stock_info(code)
            if not cfg: continue

            name = cfg.get("name", "Unknown")
            fixed_name = get_fixed_width_name(name, 10)
            msg = (f"[{time_s}] [MKT][{fixed_name}] {code:<8} | "
                   f"Bid: {bid_s:>9} | "
                   f"Last: {price_s:>9} ({vol_s:>6}) | "
                   f"Diff: {diff_s:>9} ({state.get('rate', 0.0):>5.2f}%) | "
                   f"Ask: {ask_s:>9}")
            print_log(level, msg)
            continue

        elif tr_id == "H0STCNI0": # Domestic Order
            try:
                code = row['STCK_SHRN_ISCD']
                time_v = row['STCK_CNTG_HOUR']
                time_s = f"{time_v[:2]}:{time_v[2:4]}:{time_v[4:6]}"

                logging.info(f"--- H0STCNI0 FULL DUMP ---\n{row.to_dict()}")

                cntg_yn = row['CNTG_YN']
                rctf_cls = row['RCTF_CLS']
                rfus_yn = row.get('RFUS_YN', '0')

                side = "BUY" if row['SELN_BYOV_CLS'] == '02' else "SEL"
                order_no = row['ODER_NO']

                cfg = trading_config.get_stock_info(code)

                def safe_int_format(val):
                    try:
                        if not val or str(val).strip() == "": return "0"
                        return format(int(float(val)), ",")
                    except: return "0"

                price = safe_int_format(str(row.get('CNTG_UNPR', '0')).strip())
                qty = safe_int_format(row['CNTG_QTY'])

                msg_level = PrintLevel.INFO
                extra_info = ""

                if rfus_yn in ['Y', '1']:
                    order_val = "REJ"
                    msg_level = PrintLevel.ERROR
                    remark = str(row.get('RM', '')).strip()
                    if remark: extra_info = f" ({remark})"
                elif cntg_yn == '2': order_val = "EXE"
                else:
                    if rctf_cls in ['0', '00']: order_val = "ODR"
                    elif rctf_cls in ['1', '01']: order_val = "COR"
                    elif rctf_cls in ['2', '02']: order_val = "CAN"
                    else: order_val = "OTH"

                name = cfg.get("name", row.get('CNTG_ISNM40', 'Unknown')).strip()
                fixed_name = get_fixed_width_name(name, 10)

                msg = (f"[{time_s}] [{side}][{order_val}] [{fixed_name}] {code:<6} | "
                       f"Qty: {qty:>6} | Prc: {price:>9} | No: {order_no}{extra_info}")
                print_log(msg_level, msg)
                continue
            except Exception as e:
                print_log(PrintLevel.ERROR, f"Error parsing H0STCNI0: {e}")
                continue

        elif tr_id in ["H0GSCNI0", "H0GSCNI9"]: # Overseas Order
            try:
                if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
                    raw_list = row.tolist() if hasattr(row, 'tolist') else list(row)
                    logging.debug(f"[{tr_id} RAW] {raw_list}")

                code = str(row.get('STCK_SHRN_ISCD', 'Unknown')).strip()
                if code.startswith('000') and len(code) > 8: code = code.lstrip('0') or "Unknown"

                cfg = trading_config.get_stock_info(code)
                time_v = str(row.get('STCK_CNTG_HOUR', '000000')).strip()

                if not time_v or time_v in ["0", "000000"]:
                    if cfg and cfg.get('market') in ['NASDAQ', 'NYSE', 'AMEX']:
                        from datetime import timedelta
                        time_s = (datetime.now() - timedelta(hours=14)).strftime("%H:%M:%S")
                    else:
                        time_s = datetime.now().strftime("%H:%M:%S")
                else:
                    time_s = f"{time_v[:2]}:{time_v[2:4]}:{time_v[4:6]}" if len(time_v) >= 6 else time_v.zfill(6)

                cntg_yn = str(row.get('CNTG_YN', '1')).strip()
                rctf_cls = str(row.get('RCTF_CLS', '01')).strip()
                rfus_yn = str(row.get('RFUS_YN', 'N')).strip()
                side = "BUY" if str(row.get('SELN_BYOV_CLS')) == '02' else "SEL"
                order_no = str(row.get('ODER_NO', '0'))

                def get_val(key, default=0):
                    v = row.get(key, default)
                    try: return float(v)
                    except: return 0

                price_v = get_val('CNTG_UNPR')
                if price_v >= 10000: price_v = price_v / 10000.0
                qty_v = get_val('CNTG_QTY')
                if qty_v > 1000000: qty_v = get_val('ODER_QTY')

                price = format(price_v, ",.2f")
                qty = format(qty_v, ",.0f")

                msg_level = PrintLevel.INFO
                extra_info = ""

                if rfus_yn in ['Y', '1']:
                    order_val = "REJ"
                    msg_level = PrintLevel.ERROR
                elif cntg_yn == '2': order_val = "EXE"
                else:
                    if rctf_cls in ['0', '00']: order_val = "ODR"
                    elif rctf_cls in ['1', '01']: order_val = "COR"
                    elif rctf_cls in ['2', '02']: order_val = "CAN"
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
            if i == 0: print_log(PrintLevel.DEBUG, f"Unhandled TR_ID: {tr_id}")

def inquire_account_info() -> list:
    """
    Integrated Account Info View
    3-State View: Summary -> US Portfolio -> KR Portfolio -> Summary
    """
    from account_helper import get_integrated_account_info

    # Initial Loading State
    clear_result_area()
    show_in_result_area(["Fetching integrated account data..."])

    data = get_integrated_account_info()

    # State
    view_mode = 0 # 0: Summary, 1: US List, 2: KR List
    page_idx = 0
    ROWS_PER_PAGE = 5

    # Pre-calc Summary Data
    ex_rate = data.get('exchange_rate', 0.0)

    # --- KR Summary ---
    d_asset = data['domestic_asset']
    # d_deposit removed from ui as per request, just calc values
    d_orderable = data.get('krw_orderable', 0)

    d_pl_amt = 0.0
    d_pchs_amt = 0.0
    for stock in data['domestic_stocks']:
        d_pl_amt += stock['pnl_amt']
        d_pchs_amt += (stock['avg_price'] * stock['qty'])

    d_tot_eval = d_pchs_amt + d_pl_amt
    d_pl_rate = (d_pl_amt / d_pchs_amt * 100) if d_pchs_amt > 0 else 0.0

    # --- US Summary ---
    o_asset = data['overseas_asset']
    o_orderable_usd = float(o_asset.get('frcr_drwg_psbl_amt_1', 0))

    o_pl_amt_usd = 0.0
    o_pchs_amt_usd = 0.0
    o_stock_eval_usd = 0.0

    for stock in data['overseas_stocks']:
        o_pl_amt_usd += stock['pnl_amt']
        pchs = stock['avg_price'] * stock['qty']
        o_pchs_amt_usd += pchs
        o_stock_eval_usd += (stock['cur_price'] * stock['qty'])

    o_pl_rate = (o_pl_amt_usd / o_pchs_amt_usd * 100) if o_pchs_amt_usd > 0 else 0.0

    o_tot_val_usd = o_stock_eval_usd + o_orderable_usd

    while True:
        clear_result_area()
        lines = []

        SEPARATOR_LEN = 95

        # --- VIEW 0: SUMMARY ---
        if view_mode == 0:
            lines.append("=" * SEPARATOR_LEN)
            lines.append(f" [Account Summary] exchange rate : {ex_rate:,.2f} KRW/USD")
            lines.append("=" * SEPARATOR_LEN)

            lines.append(f" [KR] Total value: {d_tot_eval:,.0f} KRW | Orderable: {d_orderable:,.0f} KRW")
            lines.append(f"      PL Amt      : {d_pl_amt:,.0f} KRW ({d_pl_rate:+.2f} %)")
            lines.append("-" * SEPARATOR_LEN)

            lines.append(f" [US] Total value: ${o_tot_val_usd:,.2f} | Orderable: ${o_orderable_usd:,.2f}")
            lines.append(f"      PL Amt      : ${o_pl_amt_usd:,.2f} ({o_pl_rate:+.2f} %)")
            lines.append("=" * SEPARATOR_LEN)

            lines.append(f" [f] Toggle View(US List)  [q] Quit")

        # --- VIEW 1 & 2: LIST ---
        else:
            is_us = (view_mode == 1)
            target_list = data['overseas_stocks'] if is_us else data['domestic_stocks']
            title = "US Stocks" if is_us else "KR Stocks"

            l_pl_amt = o_pl_amt_usd if is_us else d_pl_amt
            l_pl_rate = o_pl_rate if is_us else d_pl_rate
            l_tot_stock = o_stock_eval_usd if is_us else d_tot_eval

            total_items = len(target_list)
            total_pages = (total_items + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
            if total_pages == 0: total_pages = 1
            if page_idx >= total_pages: page_idx = 0

            lines.append("=" * SEPARATOR_LEN)
            lines.append(f" [Portfolio: {title}] ({page_idx+1}/{total_pages})")

            # Header
            header_fmt = " {:<6} | {} | {:>6} | {:>9} | {:>9} | {:>9} | {:>7}"
            hdr_name = get_fixed_width_name("Name", 20)
            lines.append(header_fmt.format("Ticker", hdr_name, "Qty", "Avg", "Cur", "P/L", "P/L%"))

            start_idx = page_idx * ROWS_PER_PAGE
            end_idx = start_idx + ROWS_PER_PAGE
            page_items = target_list[start_idx:end_idx]

            if not page_items:
                 lines.append("  (No holdings)")
                 for _ in range(ROWS_PER_PAGE-1): lines.append("")
            else:
                for item in page_items:
                    ticker = str(item.get('symbol', ''))[:6]
                    name = get_fixed_width_name(item['name'], 20)

                    if is_us:
                        q_val = item['qty']
                        qty = f"{int(q_val):,}" if q_val.is_integer() else f"{q_val:,.2f}"
                        avg = f"${item['avg_price']:,.2f}"
                        cur = f"${item['cur_price']:,.2f}"
                        pl_val = f"${item['pnl_amt']:,.2f}"
                    else:
                        qty = f"{item['qty']:,}"
                        avg = f"{item['avg_price']:,.0f}"
                        cur = f"{item['cur_price']:,.0f}"
                        pl_val = f"{item['pnl_amt']:,.0f}"

                    pnl_pct = f"{item['pnl_rate']:.2f}%"
                    lines.append(header_fmt.format(ticker, name, qty, avg, cur, pl_val, pnl_pct))

                rem = ROWS_PER_PAGE - len(page_items)
                for _ in range(rem): lines.append("")

            lines.append("-" * SEPARATOR_LEN)

            rate_str = f"{l_pl_rate:+.2f}%"
            if l_pl_amt < 0 and "0.00%" in rate_str and "+" in rate_str:
                rate_str = rate_str.replace("+", "-")

            if is_us:
                tot_str = f" Total: ${l_tot_stock:,.2f}       P/L: ${l_pl_amt:,.2f} ({rate_str})"
            else:
                tot_str = f" Total: {l_tot_stock:,.0f} KRW       P/L: {l_pl_amt:,.0f} KRW ({rate_str})"
            lines.append(tot_str)

            next_view = "KR List" if is_us else "Summary"
            lines.append(f" [n] Next Page  [f] Toggle({next_view})  [q] Quit")

        show_in_result_area(lines)

        ch = msvcrt.getch()
        if ch == b'q':
            clear_result_area() # Ensure cleared on exit
            return []
        elif ch == b'f':
            view_mode = (view_mode + 1) % 3
            page_idx = 0
        elif ch == b'n':
            if view_mode != 0:
                page_idx += 1
                if page_idx >= total_pages: page_idx = 0

    return []

def menu():
    os.system('cls' if os.name == 'nt' else 'clear')
    render_ui(full_refresh=True)

    while True:
        render_ui(full_refresh=True)
        choice = input_at(10, 2, "Enter Choice: ").strip()

        if choice == '1':
            inquire_account_info()
        elif choice == '2':
            handle_place_order()
        elif choice == '3':
            handle_manage_orders()
        # Option 4 removed
        elif choice == '0':
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

    # Load stocks to watch
    watch_list_kr = [s["ticker"] for s in trading_config.CONFIG.get("KR", []) if not s.get("disabled", False)]
    watch_list_us = [s["ticker"] for s in trading_config.CONFIG.get("US", []) if not s.get("disabled", False)]

    # Personal Notifications
    htsid = ka.getTREnv().my_htsid
    if htsid:
        ws.subscribe(ccnl_notice, htsid, kwargs={"env_dv": "real"})

    if watch_list_kr:
        ws.subscribe(asking_price_total, watch_list_kr)
        ws.subscribe(ccnl_total, watch_list_kr)

    if watch_list_us:
        formatted_us_list = []
        for ticker in watch_list_us:
            if any(ticker.startswith(p) for p in ["DNAS", "DNYS", "DAMS"]):
                formatted_us_list.append(ticker)
                continue

            info = trading_config.get_stock_info(ticker)
            market = info.get("market", "").upper()

            if market == "NASDAQ": formatted_us_list.append(f"DNAS{ticker}")
            elif market == "NYSE": formatted_us_list.append(f"DNYS{ticker}")
            elif market == "AMEX": formatted_us_list.append(f"DAMS{ticker}")
            else: formatted_us_list.append(f"DNAS{ticker}")

        ws.subscribe(asking_price, formatted_us_list)
        ws.subscribe(delayed_ccnl, formatted_us_list)

    if hasattr(ws, 'add_callback'):
        ws.add_callback(on_result)
    elif hasattr(ws, 'on'):
        ws.on("message", on_result)
    else:
        ws.callback = on_result

    ws_thread = threading.Thread(target=ws.start, args=(on_result,), daemon=True)
    ws_thread.start()

    menu()
