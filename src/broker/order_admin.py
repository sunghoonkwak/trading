# -*- coding: utf-8 -*-
"""Application-owned runtime for open-order administration."""

import logging
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from core import trading_config
from core.display import add_alert, clear_order_states, update_order_state


def _get_trenv():
    from kis.kis_api import kis_auth as ka

    return ka.getTREnv()


def _get_domestic_order_endpoints():
    from kis.kis_api.domestic_stock.inquire_psbl_rvsecncl.inquire_psbl_rvsecncl import (
        inquire_psbl_rvsecncl,
    )
    from kis.kis_api.domestic_stock.order_rvsecncl.order_rvsecncl import (
        order_rvsecncl,
    )

    return inquire_psbl_rvsecncl, order_rvsecncl


def _get_overseas_order_endpoints():
    from kis.kis_api.overseas_stock.inquire_nccs.inquire_nccs import (
        inquire_nccs as inquire_nccs_overseas,
    )
    from kis.kis_api.overseas_stock.order_rvsecncl.order_rvsecncl import (
        order_rvsecncl as order_rvsecncl_overseas,
    )

    return inquire_nccs_overseas, order_rvsecncl_overseas


def _get_toss_cancel_helpers():
    from toss.cancel_order import cancel_order
    from toss.get_holdings import _get_default_account_seq
    from toss.get_prices import load_access_token

    return load_access_token, _get_default_account_seq, cancel_order


def _fetch_toss_open_orders() -> pd.DataFrame:
    from toss.get_holdings import _get_default_account_seq
    from toss.get_orders import get_orders
    from toss.get_prices import load_access_token

    access_token = load_access_token()
    account_seq = _get_default_account_seq(access_token)
    result = get_orders(
        account_seq=account_seq,
        status="OPEN",
        access_token=access_token,
    )
    orders = result.get("orders")
    if not isinstance(orders, list) or not orders:
        return pd.DataFrame()

    df_toss = pd.DataFrame(orders)
    df_toss["_market"] = "TOSS"
    return df_toss


def _first_present(*values, default=None):
    for value in values:
        if value is None or pd.isna(value):
            continue
        if isinstance(value, str) and value.strip() in {"", "Unknown", "nan", "None"}:
            continue
        return value
    return default


def _mask_order_id(value):
    value = str(value)
    if len(value) <= 12:
        return value
    return f"{value[:6]}...{value[-6:]}"


def fetch_open_orders() -> Tuple[pd.DataFrame, int, int, int]:
    """Fetch open orders from all configured markets."""
    trenv = _get_trenv()
    cano = trenv.my_acct
    prod = trenv.my_prod
    inquire_nccs_overseas, _ = _get_overseas_order_endpoints()

    try:
        df_us = inquire_nccs_overseas(
            cano=cano,
            acnt_prdt_cd=prod,
            ovrs_excg_cd="NASD",
            sort_sqn="DS",
            FK200="",
            NK200="",
        )
        if not df_us.empty:
            df_us["_market"] = "US"
    except Exception as e:
        logging.error("[OrderAdmin] US order fetch failed: %s", e)
        df_us = pd.DataFrame()

    df_kr = pd.DataFrame()
    if trading_config.is_kis_domestic_enabled():
        inquire_psbl_rvsecncl, _ = _get_domestic_order_endpoints()
        try:
            df_kr = inquire_psbl_rvsecncl(
                cano=cano,
                acnt_prdt_cd=prod,
                inqr_dvsn_1="0",
                inqr_dvsn_2="0",
            )
            if not df_kr.empty:
                df_kr["_market"] = "KR"
        except Exception as e:
            logging.error("[OrderAdmin] KR order fetch failed: %s", e)

    try:
        df_toss = _fetch_toss_open_orders()
        if not df_toss.empty:
            df_toss["_market"] = "TOSS"
    except Exception as e:
        logging.error("[OrderAdmin] Toss order fetch failed: %s", e)
        df_toss = pd.DataFrame()

    if df_us.empty and df_kr.empty and df_toss.empty:
        return pd.DataFrame(), 0, 0, 0

    combined = pd.concat([df_us, df_kr, df_toss], ignore_index=True)
    return combined, len(df_us), len(df_kr), len(df_toss)


def execute_manage_action(
    market: str,
    action_type: str,
    order_data: Dict[str, Any],
    new_price: Optional[str] = None,
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Execute a KIS cancel (2) or correction (1) for an open order."""
    trenv = _get_trenv()
    cano = trenv.my_acct
    prod = trenv.my_prod
    _, order_rvsecncl_overseas = _get_overseas_order_endpoints()
    t_ord = {k.lower(): v for k, v in order_data.items()}
    order_no = _first_present(
        t_ord.get("odno"),
        t_ord.get("ord_no"),
        t_ord.get("orderid"),
        default="Unknown",
    )
    action_name = "CANCEL" if action_type == "2" else "CORRECT"

    logging.info(
        "[OrderAdmin] Requesting %s for order %s (%s)",
        action_name,
        _mask_order_id(order_no),
        market,
    )

    try:
        if market == "TOSS":
            if action_type != "2":
                return None, "Toss order correction is not supported"

            load_access_token, get_default_account_seq, cancel_order = _get_toss_cancel_helpers()
            access_token = load_access_token()
            account_seq = get_default_account_seq(access_token)
            result = cancel_order(
                order_id=str(order_no),
                account_seq=account_seq,
                access_token=access_token,
            )
            logging.info("[OrderAdmin] TOSS CANCEL success: %s", _mask_order_id(order_no))
            return pd.DataFrame([result]), None

        if market == "KR":
            if not trading_config.is_kis_domestic_enabled():
                return None, "KIS domestic order management is disabled"

            _, order_rvsecncl = _get_domestic_order_endpoints()
            res_df, msg = order_rvsecncl(
                env_dv="real",
                cano=cano,
                acnt_prdt_cd=prod,
                krx_fwdg_ord_orgno=t_ord.get(
                    "ord_gno_brno",
                    t_ord.get("krx_fwdg_ord_orgno", ""),
                ),
                orgn_odno=order_no,
                ord_dvsn=t_ord.get("ord_dvsn_cd", t_ord.get("ord_dvsn", "00")),
                rvse_cncl_dvsn_cd="02" if action_type == "2" else "01",
                ord_qty=t_ord.get("psbl_qty"),
                ord_unpr=new_price if action_type == "1" else "0",
                qty_all_ord_yn="Y",
                excg_id_dvsn_cd=t_ord.get("excg_id_dvsn_cd", "KRX"),
            )
        else:
            qty = t_ord.get(
                "nccs_qty",
                t_ord.get("ft_ord_qty4", t_ord.get("ord_qty", 0)),
            )
            res_df, msg = order_rvsecncl_overseas(
                cano=cano,
                acnt_prdt_cd=prod,
                ovrs_excg_cd=t_ord.get("ovrs_excg_cd", "NASD"),
                pdno=t_ord.get("pdno"),
                orgn_odno=order_no,
                rvse_cncl_dvsn_cd="02" if action_type == "2" else "01",
                ord_qty=str(qty),
                ovrs_ord_unpr=new_price if action_type == "1" else "0",
                mgco_aptm_odno="",
                ord_svr_dvsn_cd="0",
                env_dv="real",
            )

        if res_df is not None:
            logging.info(
                "[OrderAdmin] %s success: %s | Msg: %s",
                action_name,
                order_no,
                msg,
            )
        else:
            logging.warning(
                "[OrderAdmin] %s failed: %s | Msg: %s",
                action_name,
                order_no,
                msg,
            )

        return res_df, msg
    except Exception as e:
        logging.error(
            "[OrderAdmin] %s exception: %s | Error: %s",
            action_name,
            order_no,
            e,
        )
        return None, str(e)


def _sync_display_open_orders():
    add_alert("[ORD] Syncing open orders...", "INFO")
    clear_order_states()
    try:
        df, num_us, num_kr, num_toss = fetch_open_orders()
        add_alert(
            f"[ORD] updated! Orders US/KR/Toss : {num_us} / {num_kr} / {num_toss}",
            "SUCCESS",
        )
        if not df.empty:
            for _, row in df.iterrows():
                row_l = {k.lower(): v for k, v in row.items()}
                odno = _first_present(
                    row_l.get('odno'),
                    row_l.get('ord_no'),
                    row_l.get('orderid'),
                    default='Unknown',
                )
                pdno = _first_present(
                    row_l.get('pdno'),
                    row_l.get('stck_shrn_iscd'),
                    row_l.get('symbol'),
                    default='Unknown',
                )
                api_name = _first_present(
                    row_l.get('prdt_name'),
                    row_l.get('stck_nm'),
                    row_l.get('stck_nm40'),
                    row_l.get('symbolname'),
                    row_l.get('instrumentname'),
                    row_l.get('name'),
                    default='Unknown',
                )

                market = row.get('_market', 'US')
                broker = "TOSS" if market == "TOSS" else "KIS"
                if market == "TOSS" and api_name == "Unknown":
                    api_name = pdno
                if api_name != pdno:
                    trading_config.update_stock_name(pdno, api_name)
                stock_info = trading_config.get_stock_info(pdno)

                if market == "KR":
                    side = "Buy" if row_l.get('sll_buy_dvsn_cd') == '02' else "Sell"
                    price = str(int(float(row_l.get('ord_unpr', '0'))))
                    qty = str(row_l.get('psbl_qty', 0))
                elif market == "TOSS":
                    side = "Buy" if str(row_l.get('side', '')).upper() == "BUY" else "Sell"
                    p_val = row_l.get('price')
                    try:
                        p_float = float(p_val)
                        price = f"{p_float:.2f}" if p_float > 0 else "Market"
                    except Exception:
                        price = "Market"
                    q_val = next(
                        (
                            value
                            for value in (
                                row_l.get('remainingquantity'),
                                row_l.get('remaining_quantity'),
                                row_l.get('quantity'),
                                row_l.get('orderquantity'),
                            )
                            if value is not None and not pd.isna(value)
                        ),
                        0,
                    )
                    qty = str(int(float(q_val)))
                else:
                    side_text = row_l.get(
                        'sll_buy_dvsn_cd_name',
                        row_l.get('sll_buy_dvsn_name', ''),
                    ).strip()
                    if not side_text or side_text in ['?', 'nan', 'None', '']:
                        side = "Buy" if row_l.get('sll_buy_dvsn_cd') == '02' else "Sell"
                    elif "매수" in side_text:
                        side = side_text.replace("매수", " Buy")
                    elif "매도" in side_text:
                        side = side_text.replace("매도", " Sell")
                    else:
                        side = side_text

                    p_val = row_l.get(
                        'ft_ord_unpr3',
                        row_l.get(
                            'ft_ord_unpr4',
                            row_l.get('ovrs_ord_unpr', row_l.get('ord_unpr', '0')),
                        ),
                    )
                    try:
                        p_float = float(p_val)
                        price = f"{p_float:.2f}" if p_float > 0 else "Market"
                    except Exception:
                        price = "0"

                    q_val = row_l.get(
                        'nccs_qty',
                        row_l.get('ft_ord_qty4', row_l.get('ord_qty', 0)),
                    )
                    qty = str(int(float(q_val)))

                raw_time = row_l.get('ord_tmd', '')
                time_str = None
                if raw_time is not None and not pd.isna(raw_time):
                    raw_time = str(raw_time)
                else:
                    raw_time = ''
                if raw_time and len(raw_time) == 6:
                    time_str = f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:]}"

                display_name = _first_present(stock_info.get('name'), api_name, default=pdno)

                update_order_state(
                    odno,
                    pdno,
                    display_name,
                    side,
                    price,
                    qty,
                    "PLACED",
                    notify=False,
                    time_str=time_str,
                    broker=broker,
                )
        return True
    except Exception as e:
        add_alert(f"Sync failed: {e}", "ERROR")
        return None


def sync_open_orders():
    """Sync open orders into display state."""
    return _sync_display_open_orders()
