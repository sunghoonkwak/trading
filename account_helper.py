import logging
import kis_api.kis_auth as ka
import json
import time
from datetime import datetime, timedelta
import pandas as pd

def get_account_balance() -> dict:
    """
    Fetch both Domestic (KRW) and Overseas (USD) Cash Info.
    Returns a dictionary with retrieved values.
    """
    result = {
        'krw_deposit': 0,
        'krw_orderable': 0,
        'usd_deposit': 0.0,
        'usd_withdrawable': 0.0,
        'error_krw': None,
        'error_usd': None
    }

    cano = ka.getTREnv().my_acct
    acnt_prdt_cd = ka.getTREnv().my_prod

    # 1. Domestic Info (KRW)
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

    if res_krw.isOK():
        body = res_krw.getBody()
        output = getattr(body, 'output', None)
        if isinstance(output, dict):
            deposit = output.get('ord_psbl_cash') or '0'
            orderable = output.get('nrcvb_buy_amt') or '0'
            result['krw_deposit'] = int(float(deposit))
            result['krw_orderable'] = int(float(orderable))
    else:
        result['error_krw'] = res_krw.getErrorMessage()

    # 2. Overseas Info (USD)
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
            result['usd_deposit'] = float(f_deposit)
            result['usd_withdrawable'] = float(f_withdrawable)
        else:
            result['error_usd'] = "Balance info not found in output2"
    else:
        result['error_usd'] = res_usd.getErrorMessage()

    return result

def get_account_portfolio() -> dict:
    """
    Fetch current holdings for Domestic and Overseas stocks.
    Fetches only the first page (no pagination/recursion).
    Returns a dictionary with retrieved values normalized for main.py.
    """
    result = {
        "domestic": [],
        "overseas": [],
        "dom_total": {},
        "ovs_total": {},
        "dom_error": None,
        "ovs_error": None
    }

    cano = ka.getTREnv().my_acct
    acnt_prdt_cd = ka.getTREnv().my_prod

    def _get_val(d, keys, default=None):
        """Helper to get value from dict trying multiple keys"""
        if hasattr(d, '_asdict'):
            d = d._asdict()

        if isinstance(d, dict):
            for k in keys:
                if k in d:
                    return d[k]
        return default

    # --- 1. Domestic Holdings (Output1 List, Output2 Summary) ---
    url_krw = "/uapi/domestic-stock/v1/trading/inquire-balance"
    tr_id_krw = "TTTC8434R"

    params_krw = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": ""
    }

    res_krw = ka._url_fetch(url_krw, tr_id_krw, "", params_krw)

    if res_krw.isOK():
        body = res_krw.getBody()

        # Output1: Holdings List
        output1 = getattr(body, 'output1', [])
        logging.debug(f"[Domestic Output1] {json.dumps(output1, default=str, indent=4, ensure_ascii=False)}")
        raw_list = []
        if isinstance(output1, list):
            raw_list = output1
        elif isinstance(output1, dict):
            raw_list = [output1]

        # Map fields
        for item in raw_list:
            try:
                mapped = {
                    'name': _get_val(item, ['prdt_name', 'PRDT_NAME'], 'Unknown'),
                    'qty': int(_get_val(item, ['hldg_qty', 'HLDG_QTY'], 0)),
                    'avg_price': float(_get_val(item, ['pchs_avg_pric', 'PCHS_AVG_PRIC'], 0)),
                    'cur_price': float(_get_val(item, ['prpr', 'PRPR'], 0)),
                    'pnl_rate': float(_get_val(item, ['evlu_pfls_rt', 'EVLU_PFLS_RT'], 0)),
                    'symbol': _get_val(item, ['pdno', 'PDNO'], '')
                }
                if mapped['qty'] > 0:
                    result['domestic'].append(mapped)
            except Exception as e:
                logging.error(f"Error mapping domestic item: {e}")

        # Output2: Summary
        output2 = getattr(body, 'output2', [])
        logging.debug(f"[Domestic Output2] {json.dumps(output2, default=str, indent=4, ensure_ascii=False)}")
        if output2:
            if isinstance(output2, list): result['dom_total'] = output2[0]
            elif isinstance(output2, dict): result['dom_total'] = output2

    else:
        result['dom_error'] = res_krw.getErrorMessage()

    # --- 2. Overseas Holdings (Loop NASD, NYSE, AMEX) ---
    url_usd = "/uapi/overseas-stock/v1/trading/inquire-balance"
    tr_id_usd = "TTTS3012R"

    # Check 3 major exchanges
    exchanges = ["NASD", "NYSE", "AMEX"]
    seen_symbols = set()

    for excg in exchanges:
        params_usd = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "OVRS_EXCG_CD": excg,
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }

        res_usd = ka._url_fetch(url_usd, tr_id_usd, "", params_usd)

        if res_usd.isOK():
            body = res_usd.getBody()

            # Output1: Holdings List
            output1 = getattr(body, 'output1', [])
            logging.debug(f"[Overseas Output1 ({excg})] {json.dumps(output1, default=str, indent=4, ensure_ascii=False)}")
            raw_list = []
            if isinstance(output1, list):
                raw_list = output1
            elif isinstance(output1, dict):
                raw_list = [output1]

            # Map fields
            for item in raw_list:
                try:
                    symbol = _get_val(item, ['ovrs_pdno', 'OVRS_PDNO'], '')

                    # Deduplicate based on symbol
                    if symbol and symbol in seen_symbols:
                        continue

                    mapped = {
                        'name': _get_val(item, ['ovrs_item_name', 'OVRS_ITEM_NAME'], 'Unknown'),
                        'qty': float(_get_val(item, ['ovrs_cblc_qty', 'OVRS_CBLC_QTY'], 0)),
                        'avg_price': float(_get_val(item, ['pchs_avg_pric', 'PCHS_AVG_PRIC'], 0)),
                        'cur_price': float(_get_val(item, ['now_pric2', 'NOW_PRIC2'], 0)),
                        'pnl_rate': float(_get_val(item, ['evlu_pfls_rt', 'EVLU_PFLS_RT'], 0)),
                        'exchange': _get_val(item, ['ovrs_excg_cd', 'OVRS_EXCG_CD'], excg),
                        'symbol': symbol
                    }

                    if mapped['qty'] > 0:
                        result['overseas'].append(mapped)
                        if symbol:
                            seen_symbols.add(symbol)
                except Exception as e:
                    logging.error(f"Error mapping overseas item ({excg}): {e}")

            # Output2: Summary
            output2 = getattr(body, 'output2', [])
            logging.debug(f"[Overseas Output2 ({excg})] {json.dumps(output2, default=str, indent=4, ensure_ascii=False)}")
            if output2:
                if isinstance(output2, list): result['ovs_total'] = output2[0]
                elif isinstance(output2, dict): result['ovs_total'] = output2

        else:
            logging.error(f"Failed to fetch {excg}: {res_usd.getErrorMessage()}")

    return result
