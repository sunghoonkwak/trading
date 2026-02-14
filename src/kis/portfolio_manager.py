# -*- coding: utf-8 -*-
"""
Portfolio Manager Module

Handles fetching and merging account data from KIS API and Google Sheets.
"""
import logging
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

from kis.kis_api import kis_auth as ka
from kis.kis_api.domestic_stock.inquire_balance.inquire_balance import inquire_balance
from kis.kis_api.overseas_stock.inquire_present_balance.inquire_present_balance import inquire_present_balance

class PortfolioManager:
    """Orchestrates portfolio data fetching, conversion, and merging."""

    OWNERS = [
        {"id": "owner_01", "name": "곽성훈"},
        {"id": "owner_02", "name": "염인선"}
    ]

    @classmethod
    def get_integrated_portfolio(cls) -> Dict[str, Any]:
        """Main entry point to get the full integrated portfolio."""
        from kis.gsheet import connect_google_sheet, parse_worksheet_data
        from display import add_alert

        # 1. Fetch KIS Data
        add_alert("[KIS] Fetching KIS API data...", "INFO")
        kis_raw_data = cls._fetch_kis_account_data()
        
        kis_portfolio = {}
        if not kis_raw_data.get('error'):
            kis_portfolio = cls._convert_kis_to_standard(kis_raw_data)
            add_alert(f"[KIS] {len(kis_portfolio.get('holdings', []))} holdings loaded", "SUCCESS")
        else:
            add_alert(f"KIS Error: {kis_raw_data['error']}", "WARN")

        # 2. Fetch GSheet Data
        add_alert("[KIS] Fetching GSheet data...", "INFO")
        gsheet_data, gs_errors = cls._fetch_gsheet_all()
        if gs_errors:
            add_alert(f"GSheet Warning: {gs_errors}", "WARN")

        # 3. Merge and Normalize
        return cls._merge_all(kis_portfolio, gsheet_data, kis_raw_data.get('exchange_rate'), kis_raw_data.get('error'), gs_errors)

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
    def _fetch_kis_account_data(cls) -> Dict[str, Any]:
        """Fetches both domestic and overseas balances from KIS."""
        cano = ka.getTREnv().my_acct
        prod = ka.getTREnv().my_prod
        env_dv = "demo" if ka.isPaperTrading() else "real"

        # Domestic
        kr_res = {'stocks': [], 'asset': {}, 'krw_orderable': 0, 'error': None}
        try:
            df1, df2 = inquire_balance(
                env_dv=env_dv, cano=cano, acnt_prdt_cd=prod, inqr_dvsn="02", unpr_dvsn="01",
                afhr_flpr_yn="N", fund_sttl_icld_yn="N", fncg_amt_auto_rdpt_yn="N", prcs_dvsn="00"
            )
            if not df1.empty:
                for item in df1.to_dict('records'):
                    kr_res['stocks'].append({
                        'name': cls._get_val(item, ['prdt_name', 'PRDT_NAME']),
                        'qty': int(float(cls._get_val(item, ['hldg_qty', 'HLDG_QTY'], 0))),
                        'cur_price': float(cls._get_val(item, ['prpr', 'PRPR'], 0)),
                        'avg_price': float(cls._get_val(item, ['pchs_avg_pric', 'PCHS_AVG_PRIC', 'avg_unpr3'], 0)),
                        'symbol': cls._get_val(item, ['pdno', 'PDNO'], '')
                    })
            if not df2.empty:
                kr_res['asset'] = df2.iloc[0].to_dict()
                kr_res['krw_orderable'] = int(float(cls._get_val(kr_res['asset'], ['prvs_rcdl_excc_amt', 'PRVS_RCDL_EXCC_AMT'], 0)))
        except Exception as e: kr_res['error'] = str(e)

        # Overseas
        us_res = {'stocks': [], 'asset': {}, 'exchange_rate': 0.0, 'error': None}
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
                    us_res['stocks'].append({
                        'name': cls._get_val(item, ['prdt_name', 'PRDT_NAME', 'ovrs_prdt_name']),
                        'qty': float(cls._get_val(item, ['ccld_qty_smtl1', 'ovrs_cblc_qty', 'HLDG_QTY'], 0)),
                        'cur_price': float(cls._get_val(item, ['ovrs_now_pric1', 'prpr'], 0)),
                        'avg_price': float(cls._get_val(item, ['avg_unpr3', 'pchs_avg_pric'], 0)),
                        'symbol': symbol,
                        'exchange': cls._get_val(item, ['ovrs_excg_cd', 'OVRS_EXCG_CD'], 'US')
                    })
                    seen.add(symbol)
            if not df2.empty:
                us_res['asset'].update(df2.iloc[0].to_dict())
                us_res['exchange_rate'] = float(cls._get_val(us_res['asset'], ['bass_exrt', 'BASS_EXRT', 'frst_bltn_exrt'], 0))
        except Exception as e: us_res['error'] = str(e)

        return {
            'domestic_stocks': kr_res['stocks'], 'overseas_stocks': us_res['stocks'],
            'domestic_asset': kr_res['asset'], 'overseas_asset': us_res['asset'],
            'exchange_rate': us_res['exchange_rate'], 'krw_orderable': kr_res['krw_orderable'],
            'error': f"KR:{kr_res['error']} | US:{us_res['error']}" if (kr_res['error'] or us_res['error']) else None
        }

    @classmethod
    def _convert_kis_to_standard(cls, kis_data: Dict) -> Dict:
        """Converts KIS raw result to standard portfolio format."""
        holdings, asset_info, cash = [], {}, []
        kis_acc_key = "한국투자증권_owner_01"

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
            cash.append({"account_name": "한국투자증권", "amount": float(kis_data['krw_orderable']), "currency": "KRW"})
        usd_cash = float(kis_data['overseas_asset'].get('frcr_drwg_psbl_amt_1', 0))
        if usd_cash > 0:
            cash.append({"account_name": "한국투자증권", "amount": usd_cash, "currency": "USD"})

        return {
            "holdings": holdings, "cash_holdings": cash, "asset_info": asset_info,
            "accounts": {kis_acc_key: {"name": "한국투자증권", "owner_id": "owner_01"}}
        }

    @staticmethod
    def _fetch_gsheet_all() -> Tuple[Dict, Optional[str]]:
        """Fetches GSheet data for all currencies."""
        from kis.gsheet import connect_google_sheet, parse_worksheet_data
        gs_data = {"accounts": {}, "holdings": [], "asset_info": {}, "cash_holdings": []}
        errors = []
        for curr in ['USD', 'KRW']:
            sheet = connect_google_sheet(curr)
            if sheet:
                parsed = parse_worksheet_data(sheet, curr)
                gs_data["accounts"].update(parsed["accounts"])
                gs_data["holdings"].extend(parsed["holdings"])
                gs_data["asset_info"].update(parsed["asset_info"])
                gs_data["cash_holdings"].extend(parsed["cash_holdings"])
            else:
                errors.append(f"Failed to connect {curr} sheet")
        return gs_data, " | ".join(errors) if errors else None

    @classmethod
    def _merge_all(cls, kis: Dict, gs: Dict, ex_rate: float, kis_err: str, gs_err: str) -> Dict:
        """Merges everything into final standardized format."""
        all_accounts_raw = {**(kis.get("accounts", {})), **(gs.get("accounts", {}))}
        account_list, id_map = [], {}
        for idx, (key, acc) in enumerate(all_accounts_raw.items(), start=1):
            acc_id = f"acc_{idx:02d}"
            id_map[key] = acc_id
            account_list.append({"id": acc_id, "owner_id": acc["owner_id"], "name": acc["name"]})

        holdings = []
        for h in kis.get("holdings", []) + gs.get("holdings", []):
            holdings.append({
                "account_id": id_map.get(h["account_key"], "unknown"),
                "ticker": h["ticker"], "name": h.get("name", h["ticker"]),
                "qty": h["qty"], "avg_price": h["avg_price"], "cur_price": h.get("cur_price", h["avg_price"])
            })

        metadata = {"last_updated": datetime.now(timezone.utc).isoformat(), "exchange_rate": ex_rate}
        if kis_err: metadata["kis_error"] = kis_err
        if gs_err: metadata["gsheet_error"] = gs_err

        return {
            "metadata": metadata, "owners": cls.OWNERS, "accounts": account_list,
            "asset_info": {**(kis.get("asset_info", {})), **(gs.get("asset_info", {}))},
            "holdings": holdings, "cash_holdings": kis.get("cash_holdings", []) + gs.get("cash_holdings", [])
        }
