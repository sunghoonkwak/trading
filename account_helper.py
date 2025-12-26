import logging
import kis_api.kis_auth as ka
import json
import time
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
        logging.info(f"--- Orderable Raw Response ---\n{json.dumps(body._asdict(), indent=4, ensure_ascii=False)}")
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
        logging.info(f"--- Overseas Cash Raw Response ---\n{json.dumps(body._asdict(), indent=4, ensure_ascii=False)}")

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
    Uses recursive logic for Domestic 'Data changed' error.
    """
    result = {'domestic': [], 'overseas': [], 'dom_error': None, 'ovs_error': None}

    cano = ka.getTREnv().my_acct
    acnt_prdt_cd = ka.getTREnv().my_prod

    # --- 1. Domestic Stock Holdings (TTTC8434R) ---
    # Temporarily commented out due to persistent SYDB0050 server errors during settlement hours.
    """
    url_kr = "/uapi/domestic-stock/v1/trading/inquire-balance"
    dom_holdings = []
    dom_total = {}

    def fetch_domestic_loop(fk="", nk="", retry_count=0):
        if retry_count > 3: # Reduced retries
            return "Max retries exceeded (Data too unstable)"

        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": fk,
            "CTX_AREA_NK100": nk
        }

        res = ka._url_fetch(url_kr, "TTTC8434R", "N", params)
        body = res.getBody()
        err_msg = res.getErrorMessage()
        msg_cd = getattr(body, 'msg_cd', 'Unknown')

        if not res.isOK():
            if msg_cd in ["SYDB0050", "KIOK0560"] or "변경" in err_msg:
                out1 = getattr(body, 'output1', [])
                if isinstance(out1, list) and len(out1) > 0:
                    logging.info(f"[Domestic] Found {len(out1)} items despite {msg_cd}. Processing.")
                else:
                    wait_time = 3.0
                    logging.warning(f"[Domestic] System Busy ({msg_cd}). Wait {wait_time}s... ({retry_count+1}/3)")
                    time.sleep(wait_time)
                    dom_holdings.clear()
                    dom_total.clear()
                    return fetch_domestic_loop(fk="", nk="", retry_count=retry_count + 1)

            elif "조회 결과가 없습니다" in err_msg or msg_cd == "KIOK0047":
                return None
            else:
                return f"[{msg_cd}] {err_msg}"

        # Success - Parse data
        output1 = getattr(body, 'output1', [])
        if isinstance(output1, list):
            for item in output1:
                qty = int(item.get('hldg_qty', 0))
                if qty > 0:
                    dom_holdings.append({
                        'code': item.get('pdno'),
                        'name': item.get('prdt_name'),
                        'qty': qty,
                        'avg_price': float(item.get('pchs_avg_pric', 0.0)),
                        'cur_price': float(item.get('prpr', 0.0)),
                        'pnl_rate': float(item.get('evlu_pfls_rt', 0.0))
                    })

        output2 = getattr(body, 'output2', [])
        if not dom_total:
            if isinstance(output2, list) and len(output2) > 0:
                dom_total.update(output2[0])
            elif isinstance(output2, dict):
                dom_total.update(output2)

        h_tr_cont = getattr(res.getHeader(), 'tr_cont', "")
        next_fk = getattr(body, 'ctx_area_fk100', "").strip()
        next_nk = getattr(body, 'ctx_area_nk100', "").strip()

        if h_tr_cont in ["M", "F"] and next_nk:
            return fetch_domestic_loop(next_fk, next_nk, retry_count)

        return None

    err = fetch_domestic_loop()
    if err:
        result['dom_error'] = err
    result['domestic'] = dom_holdings
    result['dom_total'] = dom_total
    """
    result['dom_error'] = "Service temporarily disabled (Settlement hours)"
    result['domestic'] = []
    result['dom_total'] = {}

    # 2. Overseas Stock Holdings (Iterate Exchanges)
    url_us = "/uapi/overseas-stock/v1/trading/inquire-balance"
    exchanges = ['NASD', 'NYS', 'AMS']

    for ex in exchanges:
        params_us = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "OVRS_EXCG_CD": ex,
            "TR_MKET_CD": "00",
            "INQR_DVSN": "00",
            # Pagination keys required for Overseas
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        res_us = ka._url_fetch(url_us, "TTTS3012R", "N", params_us)

        # Retry once for currency field issue if needed
        if not res_us.isOK() and "TR_CRCY_CD" in str(res_us.getErrorMessage()):
             params_us['TR_CRCY_CD'] = "USD"
             res_us = ka._url_fetch(url_us, "TTTS3012R", "N", params_us)

        if res_us.isOK():
            body_us = res_us.getBody()
            output1 = getattr(body_us, 'output1', [])
            if isinstance(output1, list):
                for item in output1:
                    qty = float(item.get('ovrs_cblc_qty', 0))
                    if qty > 0:
                        result['overseas'].append({
                            'code': item.get('ovrs_pdno'),
                            'name': item.get('ovrs_item_name'),
                            'qty': qty,
                            'avg_price': float(item.get('pchs_avg_pric', 0.0)),
                            'cur_price': float(item.get('now_pric2', 0.0)),
                            'pnl_rate': float(item.get('evlu_pfls_rt', 0.0)),
                            'exchange': ex
                        })
        else:
            if not result['overseas']:
                 if not result['ovs_error']:
                     result['ovs_error'] = res_us.getErrorMessage()

    return result
