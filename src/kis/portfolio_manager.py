# -*- coding: utf-8 -*-
"""KIS portfolio source adapter."""
import logging
import pandas as pd
from typing import Dict, Any

from kis.kis_api import kis_auth as ka
from kis.kis_api.domestic_stock.inquire_balance.inquire_balance import inquire_balance
from kis.kis_api.overseas_stock.inquire_present_balance.inquire_present_balance import inquire_present_balance
from kis.kis_api.overseas_stock.inquire_psamount.inquire_psamount import inquire_psamount

class PortfolioManager:
    """Fetch and normalize Korea Investment Securities account data."""

    KIS_ACCOUNT_NAME = "한국투자증권"
    KIS_OWNER_ID = "owner_01"
    KIS_ACCOUNT_KEY = f"{KIS_ACCOUNT_NAME}_{KIS_OWNER_ID}"

    @classmethod
    def get_integrated_portfolio(cls, kis_only: bool = False) -> Dict[str, Any]:
        """Compatibility shim for callers that still use the old entry point."""
        from data.portfolio_integration import get_integrated_portfolio

        return get_integrated_portfolio(kis_only=kis_only)

    @staticmethod
    def _get_val(d, keys, default=None):
        """Internal helper to extract values from dict/series with multiple possible keys."""
        if hasattr(d, '_asdict'): d = d._asdict()
        if not isinstance(d, (dict, pd.Series)): return default
        for k in keys:
            if k in d:
                val = d[k]
                if val is not None and str(val).lower() != 'none': return val
        return default

    @classmethod
    def _to_float(cls, d, keys, default=0.0) -> float:
        raw_value = cls._get_val(d, keys, default)
        try:
            return float(str(raw_value).replace(',', ''))
        except (TypeError, ValueError):
            return float(default)

    @classmethod
    def _to_int(cls, d, keys, default=0) -> int:
        return int(cls._to_float(d, keys, default))

    @classmethod
    def _get_positive_float_from_frames(cls, frames, keys) -> float:
        """Return the first positive numeric value found in API output frames."""
        for frame in frames:
            if frame is None or frame.empty:
                continue
            for item in frame.to_dict('records'):
                raw_value = cls._get_val(item, keys)
                try:
                    value = float(str(raw_value).replace(',', ''))
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    return value
        return 0.0

    @classmethod
    def _fetch_kis_account_data(cls) -> Dict[str, Any]:
        """Fetches both domestic and overseas balances from KIS."""
        trenv = ka.getTREnv()
        cano = trenv.my_acct
        prod = trenv.my_prod
        env_dv = "real"

        # Domestic
        kr_res = {'stocks': [], 'asset': {}, 'krw_orderable': 0, 'error': None}
        try:
            df1, df2 = inquire_balance(
                env_dv=env_dv, cano=cano, acnt_prdt_cd=prod, inqr_dvsn="02", unpr_dvsn="01",
                afhr_flpr_yn="N", fund_sttl_icld_yn="N", fncg_amt_auto_rdpt_yn="N", prcs_dvsn="00"
            )
            if not df1.empty:
                for item in df1.to_dict('records'):
                    try:
                        kr_res['stocks'].append({
                            'name': cls._get_val(item, ['prdt_name', 'PRDT_NAME']),
                            'qty': cls._to_int(item, ['hldg_qty', 'HLDG_QTY']),
                            'cur_price': cls._to_float(item, ['prpr', 'PRPR']),
                            'avg_price': cls._to_float(item, ['pchs_avg_pric', 'PCHS_AVG_PRIC', 'avg_unpr3']),
                            'symbol': cls._get_val(item, ['pdno', 'PDNO'], '')
                        })
                    except Exception as e:
                        logging.warning("[KIS] Skipping malformed domestic holding: %s", e)
            if not df2.empty:
                kr_res['asset'] = df2.iloc[0].to_dict()
                kr_res['krw_orderable'] = cls._to_int(
                    kr_res['asset'],
                    ['prvs_rcdl_excc_amt', 'PRVS_RCDL_EXCC_AMT'],
                )
        except Exception as e: kr_res['error'] = str(e)

        # Overseas
        us_res = {
            'stocks': [],
            'asset': {},
            'exchange_rate': 0.0,
            'usd_orderable': None,
            'error': None
        }
        try:
            df1, df2, df3 = inquire_present_balance(
                cano=cano, acnt_prdt_cd=prod, wcrc_frcr_dvsn_cd="02", env_dv=env_dv,
                natn_cd="000", tr_mket_cd="00", inqr_dvsn_cd="00"
            )
            if not df1.empty:
                seen = set()
                for item in df1.to_dict('records'):
                    symbol = cls._get_val(item, ['pdno', 'PDNO']) or cls._get_val(item, ['ovrs_pdno', 'OVRS_PDNO'])
                    if not symbol or symbol in seen: continue
                    try:
                        us_res['stocks'].append({
                            'name': cls._get_val(item, ['prdt_name', 'PRDT_NAME', 'ovrs_prdt_name']),
                            'qty': cls._to_float(item, ['ccld_qty_smtl1', 'ovrs_cblc_qty', 'HLDG_QTY']),
                            'cur_price': cls._to_float(item, ['ovrs_now_pric1', 'prpr']),
                            'avg_price': cls._to_float(item, ['avg_unpr3', 'pchs_avg_pric']),
                            'symbol': symbol,
                            'exchange': cls._get_val(item, ['ovrs_excg_cd', 'OVRS_EXCG_CD'], 'US')
                        })
                        seen.add(symbol)
                    except Exception as e:
                        logging.warning("[KIS] Skipping malformed overseas holding: %s", e)
            if not df2.empty:
                us_res['asset'].update(df2.iloc[0].to_dict())
            us_res['exchange_rate'] = cls._get_positive_float_from_frames(
                (df1, df2),
                ['bass_exrt', 'BASS_EXRT', 'frst_bltn_exrt', 'FRST_BLTN_EXRT']
            )
            try:
                psamount_df = inquire_psamount(
                    cano=cano,
                    acnt_prdt_cd=prod,
                    ovrs_excg_cd="NASD",
                    ovrs_ord_unpr="1",
                    item_cd="QQQM",
                    env_dv=env_dv,
                )
                us_res['usd_orderable'] = cls._get_positive_float_from_frames(
                    (psamount_df,),
                    ['ovrs_ord_psbl_amt', 'OVRS_ORD_PSBL_AMT']
                )
            except Exception as e:
                logging.warning(
                    "[KIS] Failed to fetch orderable USD from inquire_psamount: %s",
                    e
                )
        except Exception as e: us_res['error'] = str(e)

        return {
            'domestic_stocks': kr_res['stocks'], 'overseas_stocks': us_res['stocks'],
            'domestic_asset': kr_res['asset'], 'overseas_asset': us_res['asset'],
            'exchange_rate': us_res['exchange_rate'], 'krw_orderable': kr_res['krw_orderable'],
            'usd_orderable': us_res['usd_orderable'],
            'error': f"KR:{kr_res['error']} | US:{us_res['error']}" if (kr_res['error'] or us_res['error']) else None
        }

    @classmethod
    def _convert_kis_to_standard(cls, kis_data: Dict) -> Dict:
        """Converts KIS raw result to standard portfolio format."""
        holdings, asset_info, cash = [], {}, []
        kis_acc_key = cls.KIS_ACCOUNT_KEY

        # Stocks
        for s in kis_data['domestic_stocks'] + kis_data['overseas_stocks']:
            ticker = s.get('symbol', '')
            if not ticker or s.get('qty', 0) <= 0: continue
            is_us = ticker in [x.get('symbol') for x in kis_data['overseas_stocks']]

            asset_info[ticker] = {
                "name": s.get('name', ticker), "market": "US" if is_us else "KR",
                "asset_type": "Stock", "currency": "USD" if is_us else "KRW"
            }
            holdings.append({
                "account_key": kis_acc_key, "ticker": ticker, "name": s.get('name', ticker),
                "qty": s['qty'], "avg_price": s['avg_price'], "cur_price": s['cur_price']
            })

        # Cash
        if kis_data['krw_orderable'] > 0:
            cash.append({"account_name": cls.KIS_ACCOUNT_NAME, "account_key": kis_acc_key, "amount": float(kis_data['krw_orderable']), "currency": "KRW"})
        fallback_usd_cash = cls._get_val(
            kis_data['overseas_asset'],
            ['frcr_drwg_psbl_amt_1', 'ovrs_relt_proc_amt'],
            0
        )
        usd_orderable = kis_data.get('usd_orderable')
        usd_cash = float(
            fallback_usd_cash if usd_orderable is None else usd_orderable
        )
        if usd_cash > 0:
            cash.append({"account_name": cls.KIS_ACCOUNT_NAME, "account_key": kis_acc_key, "amount": usd_cash, "currency": "USD"})

        return {
            "holdings": holdings, "cash_holdings": cash, "asset_info": asset_info,
            "accounts": {kis_acc_key: {"name": cls.KIS_ACCOUNT_NAME, "owner_id": cls.KIS_OWNER_ID}}
        }
