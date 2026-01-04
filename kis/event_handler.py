# -*- coding: utf-8 -*-
"""
Packet handling event logic for KIS WebSocket.
Moves on_result logic out of main.py to solve circular dependencies.
"""
import logging
import pandas as pd
from datetime import datetime

import trading_state
import trading_config
from trading_config import strip_market_prefix
from kis import event_pipe
from kis.event_pipe import PrintLevel, print_viewer
from display import get_fixed_width_name, add_alert, remove_order_state
from menu.handle_manage_orders import request_sync
from telegram_bot.telegram_utils import send_notification


def _handle_domestic_market(tr_id: str, row) -> bool:
    """Handle domestic market data (H0UNASP0: orderbook, H0UNCNT0: tick)."""
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
            if state['ask'] == new_ask and state['bid'] == new_bid:
                return True  # Skip unchanged
            state['ask'] = new_ask
            state['bid'] = new_bid
        except:
            return True

    elif tr_id == "H0UNCNT0":
        state['time'] = row['STCK_CNTG_HOUR']
        try:
            state['price'] = int(float(row['STCK_PRPR']))
            state['vol'] = int(float(row['CNTG_VOL']))
            state['change'] = int(float(row['PRDY_VRSS']))
            state['rate'] = float(row['PRDY_CTRT'])
            sign = row['PRDY_VRSS_SIGN']
            state['sign_str'] = "+" if sign in ['1', '2'] else "-" if sign in ['4', '5'] else " "
            level = PrintLevel.INFO
            trading_state.notify_data_received()
        except:
            return True

    time_v = str(state.get('time', '000000')).strip()
    time_s = f"{time_v[:2]}:{time_v[2:4]}:{time_v[4:6]}" if len(time_v) == 6 else time_v.zfill(6)

    cfg = trading_config.get_stock_info(code)
    if not cfg:
        return True

    name = cfg.get("name", "Unknown")
    fixed_name = get_fixed_width_name(name, 20)
    bid_s = format(state.get('bid', 0), ",")
    ask_s = format(state.get('ask', 0), ",")
    price_v = state.get('price', 0)
    price_s = format(price_v, ",") if price_v > 0 else "-------"
    vol_s = format(state.get('vol', 0), ",")
    diff_s = format(state.get('change', 0), ',')

    msg = (f"{time_s}|{fixed_name}|{code:<6}|"
           f"Bid:{bid_s:>9}|"
           f"Last:{price_s:>9}({vol_s:>6})|"
           f"Diff:{diff_s:>6}({state.get('rate', 0.0):>5.2f}%)|"
           f"Ask:{ask_s:>9}")
    print_viewer(level, msg)
    return True


def _handle_overseas_market(tr_id: str, row) -> bool:
    """Handle overseas market data (HDFSASP0: orderbook, HDFSCNT0: tick)."""
    code = row.get('symb', row.get('SYMB'))
    if not code:
        return True

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
        except:
            return True

    elif tr_id == "HDFSCNT0":
        state['time'] = row.get('XHMS', '000000')
        try:
            state['price'] = float(row['LAST'])
            state['change'] = float(row['DIFF'])
            state['rate'] = float(row['RATE'])
            state['vol'] = float(row['EVOL'])
            if 'PBID' in row:
                state['bid'] = float(row['PBID'])
            if 'PASK' in row:
                state['ask'] = float(row['PASK'])
            sign = row.get('SIGN', '3')
            state['sign_str'] = "+" if sign in ['1', '2'] else "-" if sign in ['4', '5'] else " "
            level = PrintLevel.INFO
            trading_state.notify_data_received()
        except:
            return True

    time_v = str(state.get('time', '000000')).strip()
    time_s = f"{time_v[:2]}:{time_v[2:4]}:{time_v[4:6]}" if len(time_v) >= 6 else time_v.zfill(6)

    cfg = trading_config.get_stock_info(code)
    if not cfg:
        return True

    name = cfg.get("name", "Unknown")
    fixed_name = get_fixed_width_name(name, 20)
    display_code = strip_market_prefix(code)
    bid_s = format(state.get('bid', 0.0), ",.2f") if state.get('bid', 0) > 0 else "0"
    ask_s = format(state.get('ask', 0.0), ",.2f") if state.get('ask', 0) > 0 else "0"
    price_v = state.get('price', 0.0)
    price_s = format(price_v, ",.2f") if price_v > 0 else "-------"
    vol_v = state.get('vol', 0.0)
    vol_s = format(vol_v, ",.0f") if vol_v > 0 else "0"
    diff_s = format(state.get('change', 0.0), ',.2f')

    msg = (f"{time_s}|{fixed_name}|{display_code:<6}|"
           f"Bid:{bid_s:>9}|"
           f"Last:{price_s:>9}({vol_s:>6})|"
           f"Diff:{diff_s:>6}({state.get('rate', 0.0):>5.2f}%)|"
           f"Ask:{ask_s:>9}")
    print_viewer(level, msg)
    return True


def _handle_domestic_order(row) -> bool:
    """Handle domestic order notifications (H0STCNI0)."""
    try:
        code = row['STCK_SHRN_ISCD']
        time_v = row['STCK_CNTG_HOUR']
        time_s = f"{time_v[:2]}:{time_v[2:4]}:{time_v[4:6]}"

        logging.info(f"--- H0STCNI0 FULL DUMP ---\n{row.to_dict()}")

        cntg_yn = row['CNTG_YN']
        rctf_cls = row['RCTF_CLS']
        rfus_yn = row.get('RFUS_YN', '0')
        order_no = row['ODER_NO']

        cfg = trading_config.get_stock_info(code)

        def safe_int_format(val):
            try:
                if not val or str(val).strip() == "":
                    return "0"
                return format(int(float(val)), ",")
            except:
                return "0"

        price = safe_int_format(str(row.get('CNTG_UNPR', '0')).strip())
        qty = safe_int_format(row['CNTG_QTY'])

        extra_info = ""
        if rfus_yn in ['Y', '1']:
            order_val = "REJ"
            remark = str(row.get('RM', '')).strip()
            if remark:
                extra_info = f" ({remark})"
        elif cntg_yn == '2':
            order_val = "EXE"
        else:
            if rctf_cls in ['0', '00']:
                order_val = "ODR"
            elif rctf_cls in ['1', '01']:
                order_val = "COR"
            elif rctf_cls in ['2', '02']:
                order_val = "CAN"
            else:
                order_val = "OTH"

        name = cfg.get("name", row.get('CNTG_ISNM40', 'Unknown')).strip()
        fixed_name = get_fixed_width_name(name, 20)
        side_code = "BUY" if row['SELN_BYOV_CLS'] == '02' else "SEL"

        msg = (f"{time_s}|{side_code}|{order_val}|{fixed_name}|{code:<6}|"
               f"Qty:{qty:>6}|Prc:{price:>9}|No:{order_no}{extra_info}")
        logging.info(msg)

        # Use descriptive side text if available
        side_desc = str(row.get('SLL_BUY_DVSN_CD_NAME', row.get('SLL_BUY_DVSN_NAME', ''))).strip()
        if side_desc and side_desc not in ['', '?', 'nan', 'None']:
            side = side_desc
        else:
            side = "Buy" if row['SELN_BYOV_CLS'] == '02' else "Sell"

        # Notify via alert area
        tag = order_val
        add_alert(f"[{tag}] {side} {code} {qty} @ {price}", level="INFO" if tag != "REJ" else "ERROR")

        # Send to Telegram
        emoji = {"ODR": "📝", "EXE": "✅", "CAN": "❌", "COR": "✏️", "REJ": "🚫"}.get(tag, "📌")
        send_notification(f"{emoji} <b>{tag}</b> {side} {code}\nQty: {qty} @ {price}")

        # Immediate UI update: remove from list if canceled or executed
        if tag in ["CAN", "EXE"]:
            remove_order_state(order_no)

        # Delayed auto-sync with debouncing
        request_sync()
        return True
    except Exception as e:
        print_viewer(PrintLevel.ERROR, f"Error parsing H0STCNI0: {e}")
        return True


def _handle_overseas_order(tr_id: str, row) -> bool:
    """Handle overseas order notifications (H0GSCNI0, H0GSCNI9)."""
    try:
        if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
            raw_list = row.tolist() if hasattr(row, 'tolist') else list(row)
            logging.debug(f"[{tr_id} RAW] {raw_list}")

        code = str(row.get('STCK_SHRN_ISCD', 'Unknown')).strip()
        if code.startswith('000') and len(code) > 8:
            code = code.lstrip('0') or "Unknown"

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
        order_no = str(row.get('ODER_NO', '0'))

        def get_val(key, default=0):
            v = row.get(key, default)
            try:
                return float(v)
            except:
                return 0

        price_v = get_val('CNTG_UNPR')
        if price_v >= 10000:
            price_v = price_v / 10000.0
        qty_v = get_val('CNTG_QTY')
        if qty_v > 1000000:
            qty_v = get_val('ODER_QTY')

        price = f"${price_v:,.2f}"
        qty = format(qty_v, ",.0f")

        if rfus_yn in ['Y', '1']:
            order_val = "REJ"
        elif cntg_yn == '2':
            order_val = "EXE"
        else:
            if rctf_cls in ['0', '00']:
                order_val = "ODR"
            elif rctf_cls in ['1', '01']:
                order_val = "COR"
            elif rctf_cls in ['2', '02']:
                order_val = "CAN"
            else:
                order_val = "OTH"

        # For US stocks, ODER_KIND2 represents the order type
        kind_code = str(row.get('ODER_KIND2', '')).strip().upper()
        kind_map = {
            '2': '',  # Normal Limit
            'D': 'LOC',
            'E': 'MOO',
            'F': 'LOO',
            'G': 'MOC',
            '32': 'MOX',
            '34': 'LOC'
        }
        type_val = kind_map.get(kind_code, '')

        is_buy = str(row.get('SELN_BYOV_CLS', row.get('SELN_BYOV_CLS_CD', ''))) == '02'
        base_side = "Buy" if is_buy else "Sell"

        if type_val:
            side = f"{type_val} {base_side}"
        else:
            side_val = str(row.get('SLL_BUY_DVSN_CD_NAME', row.get('SLL_BUY_DVSN_NAME', ''))).strip()
            if side_val and side_val not in ['', '?', 'nan', 'None']:
                side = side_val
            else:
                side = base_side

        name = cfg.get("name", row.get('CNTG_ISNM', 'Unknown')).strip()
        fixed_name = get_fixed_width_name(name, 20)

        msg = (f"{time_s}|{side}|{order_val}|{fixed_name}|{code:<8}|"
               f"Qty:{qty:>6}|Prc:{price:>9}|No:{order_no}")
        logging.info(msg)

        # Notify via alert area
        tag = order_val
        add_alert(f"[{tag}] {side} {code} {qty} @ {price}", level="INFO" if tag != "REJ" else "ERROR")

        # Send to Telegram
        emoji = {"ODR": "📝", "EXE": "✅", "CAN": "❌", "COR": "✏️", "REJ": "🚫"}.get(tag, "📌")
        send_notification(f"{emoji} <b>{tag}</b> {side} {code}\nQty: {qty} @ {price}")

        # Immediate UI update: remove from list if canceled or executed
        if tag in ["CAN", "EXE"]:
            remove_order_state(order_no)

        # Delayed auto-sync with debouncing
        request_sync()
        return True
    except Exception as e:
        print_viewer(PrintLevel.ERROR, f"Error parsing overseas notification: {e}")
        return True


def on_result(ws, tr_id, df: pd.DataFrame, dm: dict):
    """Main WebSocket result handler - routes to specific handlers by tr_id."""
    # Handle PINGPONG for testing (displays even when market is closed)
    if tr_id == "PINGPONG":
        time_s = datetime.now().strftime("%H:%M:%S")
        print_viewer(PrintLevel.INFO, f"[{time_s}] [SYS] PINGPONG received")
        return

    if df.empty:
        print_viewer(PrintLevel.ERROR, f"System Message received for TR: {tr_id}")
        return

    tr_id = tr_id.strip()
    for i in range(len(df)):
        row = df.iloc[i]

        if tr_id in ["H0UNASP0", "H0UNCNT0"]:
            _handle_domestic_market(tr_id, row)

        elif tr_id in ["HDFSASP0", "HDFSCNT0"]:
            _handle_overseas_market(tr_id, row)

        elif tr_id == "H0STCNI0":
            _handle_domestic_order(row)

        elif tr_id in ["H0GSCNI0", "H0GSCNI9"]:
            _handle_overseas_order(tr_id, row)

        else:
            if i == 0:
                print_viewer(PrintLevel.DEBUG, f"Unhandled TR_ID: {tr_id}")
