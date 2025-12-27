import logging
import kis_api.kis_auth as ka
import json
import time
from datetime import datetime, timedelta
import pandas as pd

def get_integrated_account_info() -> dict:
    """
    Fetch Integrated Account Info (Cash + Portfolio)

    1. Domestic Balance (TTTC8434R): Stocks & Total Asset
    2. Overseas Present (CTRP6504R): Stocks, Asset & Exchange Rate

    Returns:
        {
            'domestic_stocks': [],
            'overseas_stocks': [],
            'domestic_asset': {},
            'overseas_asset': {},
            'exchange_rate': 0.0,
            'krw_orderable': 0,
            'error': None
        }
    """
    result = {
        'domestic_stocks': [],
        'overseas_stocks': [],
        'domestic_asset': {},
        'overseas_asset': {},
        'exchange_rate': 0.0,
        'krw_orderable': 0,
        'error': None
    }

    cano = ka.getTREnv().my_acct
    acnt_prdt_cd = ka.getTREnv().my_prod

    def _get_val(d, keys, default=None):
        if hasattr(d, '_asdict'): d = d._asdict()
        if isinstance(d, dict):
            for k in keys:
                if k in d: return d[k]
        return default

    # --- 1. Domestic Stock & Asset: inquire-balance (TTTC8434R) ---
    url_kr = "/uapi/domestic-stock/v1/trading/inquire-balance"
    tr_id_kr = "TTTC8434R"
    params_kr = {
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

    res_kr = ka._url_fetch(url_kr, tr_id_kr, "", params_kr)
    if res_kr.isOK():
        body = res_kr.getBody()
        out1 = getattr(body, 'output1', [])
        out2 = getattr(body, 'output2', [])

        logging.debug(f"[Domestic Integrated Out1] {json.dumps(out1, default=str, indent=4, ensure_ascii=False)}")
        logging.debug(f"[Domestic Integrated Out2] {json.dumps(out2, default=str, indent=4, ensure_ascii=False)}")

        raw_list = out1 if isinstance(out1, list) else [out1]
        for item in raw_list:
            try:
                mapped = {
                    'name': _get_val(item, ['prdt_name', 'PRDT_NAME'], 'Unknown'),
                    'qty': int(_get_val(item, ['hldg_qty', 'HLDG_QTY'], 0)),
                    'cur_price': float(_get_val(item, ['prpr', 'PRPR'], 0)),
                    'avg_price': float(_get_val(item, ['pchs_avg_pric', 'PCHS_AVG_PRIC'], 0)),
                    'pnl_rate': float(_get_val(item, ['evlu_pfls_rt', 'EVLU_PFLS_RT'], 0)),
                    'pnl_amt': float(_get_val(item, ['evlu_pfls_amt', 'EVLU_PFLS_AMT'], 0)),
                    'symbol': _get_val(item, ['pdno', 'PDNO'], '')
                }
                if mapped['qty'] > 0:
                    result['domestic_stocks'].append(mapped)
            except: pass

        if out2:
            d_asset = out2[0] if isinstance(out2, list) else out2
            result['domestic_asset'] = d_asset
            # User requested using 'prvs_rcdl_excc_amt' (Deposit/Orderable approximation)
            try: result['krw_orderable'] = int(float(_get_val(d_asset, ['prvs_rcdl_excc_amt', 'PRVS_RCDL_EXCC_AMT'], 0)))
            except: result['krw_orderable'] = 0

    else:
        result['error'] = f"Domestic(Bal) Error: {res_kr.getErrorMessage()}"



    # --- 2. Overseas: inquire-present-balance (CTRP6504R) ---
    url_us = "/uapi/overseas-stock/v1/trading/inquire-present-balance"
    tr_id_us = "CTRP6504R"
    params_us = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "WCRC_FRCR_DVSN_CD": "02",
        "NATN_CD": "000",
        "TR_MKET_CD": "00",
        "INQR_DVSN_CD": "00"
    }

    res_us = ka._url_fetch(url_us, tr_id_us, "N", params_us)
    if res_us.isOK():
        body = res_us.getBody()
        out1 = getattr(body, 'output1', [])
        out2 = getattr(body, 'output2', [])
        out3 = getattr(body, 'output3', [])

        logging.debug(f"[Overseas Integrated Out1] {json.dumps(out1, default=str, indent=4, ensure_ascii=False)}")
        logging.debug(f"[Overseas Integrated Out2] {json.dumps(out2, default=str, indent=4, ensure_ascii=False)}")
        logging.debug(f"[Overseas Integrated Out3] {json.dumps(out3, default=str, indent=4, ensure_ascii=False)}")

        # Exchange Rate Check (from output1 first item usually, or output2)
        # Log showed: "bass_exrt": "1460.60000000" in output1 item.
        # Output2 has "frst_bltn_exrt": "1460.60000000"

        ex_rate = 0.0

        # Overseas Stocks (Output1)
        raw_list = out1 if isinstance(out1, list) else [out1]
        seen_ovs = set()
        for item in raw_list:
            try:
                # Exchange Rate extraction (Opportunistic)
                if ex_rate == 0.0:
                    r1 = _get_val(item, ['bass_exrt', 'BASS_EXRT'], 0)
                    if r1: ex_rate = float(r1)

                symbol = _get_val(item, ['pdno', 'PDNO'], '')
                if not symbol: symbol = _get_val(item, ['ovrs_pdno', 'OVRS_PDNO'], '')

                if symbol in seen_ovs: continue

                mapped = {
                    'name': _get_val(item, ['prdt_name', 'PRDT_NAME'], 'Unknown'),
                    'qty': float(_get_val(item, ['ccld_qty_smtl1', 'CCLD_QTY_SMTL1'],
                                _get_val(item, ['ovrs_cblc_qty', 'OVRS_CBLC_QTY'], 0))),
                    'cur_price': float(_get_val(item, ['ovrs_now_pric1', 'OVRS_NOW_PRIC1'], 0)),
                    'avg_price': float(_get_val(item, ['pchs_avg_pric', 'PCHS_AVG_PRIC'], 0)),
                    'pnl_rate': float(_get_val(item, ['evlu_pfls_rt1', 'EVLU_PFLS_RT1'], 0)),
                    'pnl_amt': float(_get_val(item, ['evlu_pfls_amt2', 'EVLU_PFLS_AMT2'], 0)), # USD P/L
                    'symbol': symbol,
                    'exchange': _get_val(item, ['ovrs_excg_cd', 'OVRS_EXCG_CD'], 'US')
                }

                if mapped['qty'] > 0:
                    result['overseas_stocks'].append(mapped)
                    seen_ovs.add(symbol)
            except: pass

        # Overseas Asset
        asset = {}
        if out2:
            o2 = out2[0] if isinstance(out2, list) else out2
            asset.update(o2)
            if ex_rate == 0.0:
                r2 = _get_val(o2, ['frst_bltn_exrt', 'FRST_BLTN_EXRT'], 0)
                if r2: ex_rate = float(r2)

        if out3:
            o3 = out3[0] if isinstance(out3, list) else out3
            asset.update(o3)

        result['overseas_asset'] = asset
        result['exchange_rate'] = ex_rate

    else:
        err = f"Overseas Error: {res_us.getErrorMessage()}"
        if result['error']: result['error'] += " | " + err
        else: result['error'] = err

    return result
