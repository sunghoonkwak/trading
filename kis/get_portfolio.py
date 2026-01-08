# -*- coding: utf-8 -*-
"""
KIS Get Portfolio Module

This module handles fetching account data from KIS API.
These functions run in the KIS Thread context and should NOT be called directly
from the Main Thread - use data_service.get_portfolio_data() instead.
"""
import logging
import pandas as pd
from kis.kis_api import kis_auth as ka
from kis.kis_api.domestic_stock.inquire_balance.inquire_balance import inquire_balance
from kis.kis_api.overseas_stock.inquire_present_balance.inquire_present_balance import inquire_present_balance


def _get_val(d, keys, default=None):
    """Helper function to extract values from dict with multiple possible keys."""
    if hasattr(d, '_asdict'): d = d._asdict()
    if not isinstance(d, (dict, pd.Series)): return default
    for k in keys:
        if k in d:
            val = d[k]
            if val is None or str(val).lower() == 'none': continue
            return val
    return default


def _fetch_domestic_balance() -> dict:
    """Fetch Domestic Stock Balance and Assets (TTTC8434R)."""
    cano = ka.getTREnv().my_acct
    acnt_prdt_cd = ka.getTREnv().my_prod
    env_dv = "demo" if ka.isPaperTrading() else "real"

    result = {
        'stocks': [],
        'asset': {},
        'krw_orderable': 0,
        'error': None
    }

    df1, df2 = inquire_balance(
        env_dv=env_dv, cano=cano, acnt_prdt_cd=acnt_prdt_cd,
        afhr_flpr_yn="N", inqr_dvsn="02", unpr_dvsn="01",
        fund_sttl_icld_yn="N", fncg_amt_auto_rdpt_yn="N", prcs_dvsn="00"
    )

    if not df1.empty:
        for item in df1.to_dict('records'):
            try:
                mapped = {
                    'name': _get_val(item, ['prdt_name', 'PRDT_NAME'], 'Unknown'),
                    'qty': int(float(_get_val(item, ['hldg_qty', 'HLDG_QTY'], 0))),
                    'cur_price': float(_get_val(item, ['prpr', 'PRPR'], 0)),
                    'avg_price': float(_get_val(item, ['pchs_avg_pric', 'PCHS_AVG_PRIC', 'avg_unpr3'], 0)),
                    'pnl_rate': float(_get_val(item, ['evlu_pfls_rt', 'EVLU_PFLS_RT'], 0)),
                    'pnl_amt': float(_get_val(item, ['evlu_pfls_amt', 'EVLU_PFLS_AMT'], 0)),
                    'symbol': _get_val(item, ['pdno', 'PDNO'], '')
                }
                if mapped['qty'] > 0:
                    result['stocks'].append(mapped)
            except Exception as e:
                logging.debug(f"Domestic stock mapping error: {e}")

    if not df2.empty:
        d_asset = df2.iloc[0].to_dict()
        result['asset'] = d_asset
        try: result['krw_orderable'] = int(float(_get_val(d_asset, ['prvs_rcdl_excc_amt', 'PRVS_RCDL_EXCC_AMT'], 0)))
        except: pass
    elif df1.empty:
        result['error'] = "No data returned from KR balance inquiry."

    return result


def _fetch_overseas_balance() -> dict:
    """Fetch Overseas Stock Balance and Assets (CTRP6504R)."""
    cano = ka.getTREnv().my_acct
    acnt_prdt_cd = ka.getTREnv().my_prod
    env_dv = "demo" if ka.isPaperTrading() else "real"

    result = {
        'stocks': [],
        'asset': {},
        'exchange_rate': 0.0,
        'error': None
    }

    df1, df2, df3 = inquire_present_balance(
        cano=cano, acnt_prdt_cd=acnt_prdt_cd,
        wcrc_frcr_dvsn_cd="02", natn_cd="000",
        tr_mket_cd="00", inqr_dvsn_cd="00", env_dv=env_dv
    )

    ex_rate = 0.0
    if not df1.empty:
        seen_ovs = set()
        for item in df1.to_dict('records'):
            try:
                if ex_rate == 0.0:
                    ex_rate = float(_get_val(item, ['bass_exrt', 'BASS_EXRT'], 0))

                symbol = _get_val(item, ['pdno', 'PDNO'], '') or _get_val(item, ['ovrs_pdno', 'OVRS_PDNO'], '')
                if not symbol or symbol in seen_ovs:
                    continue

                mapped = {
                    'name': _get_val(item, ['prdt_name', 'PRDT_NAME', 'ovrs_prdt_name'], 'Unknown'),
                    'qty': float(_get_val(item, ['ccld_qty_smtl1', 'CCLD_QTY_SMTL1', 'ovrs_cblc_qty', 'HLDG_QTY'], 0)),
                    'cur_price': float(_get_val(item, ['ovrs_now_pric1', 'OVRS_NOW_PRIC1', 'prpr'], 0)),
                    'avg_price': float(_get_val(item, ['avg_unpr3', 'pchs_avg_pric', 'PCHS_AVG_PRIC', 'avg_unpr1'], 0)),
                    'pnl_rate': float(_get_val(item, ['evlu_pfls_rt1', 'EVLU_PFLS_RT1', 'evlu_pfls_rt'], 0)),
                    'pnl_amt': float(_get_val(item, ['evlu_pfls_amt2', 'EVLU_PFLS_AMT2', 'evlu_pfls_amt'], 0)),
                    'symbol': symbol,
                    'exchange': _get_val(item, ['ovrs_excg_cd', 'OVRS_EXCG_CD'], 'US')
                }
                if mapped['qty'] > 0:
                    result['stocks'].append(mapped)
                    seen_ovs.add(symbol)
            except Exception as e:
                logging.debug(f"Overseas stock mapping error: {e}")

    asset = {}
    if not df2.empty:
        o2 = df2.iloc[0].to_dict()
        asset.update(o2)
        if ex_rate == 0.0:
            ex_rate = float(_get_val(o2, ['frst_bltn_exrt', 'FRST_BLTN_EXRT'], 0))
    if not df3.empty:
        o3 = df3.iloc[0].to_dict()
        asset.update(o3)

    result['asset'] = asset
    result['exchange_rate'] = ex_rate
    if df1.empty and df2.empty:
        result['error'] = "No data returned from US balance inquiry."

    return result


def _fetch_account_data() -> dict:
    """
    Fetch all necessary data for account info.

    Returns:
        dict with domestic_stocks, overseas_stocks, exchange_rate, etc.
    """
    kr = _fetch_domestic_balance()
    us = _fetch_overseas_balance()

    return {
        'domestic_stocks': kr['stocks'],
        'overseas_stocks': us['stocks'],
        'domestic_asset': kr['asset'],
        'overseas_asset': us['asset'],
        'exchange_rate': us['exchange_rate'],
        'krw_orderable': kr['krw_orderable'],
        'error': f"{kr['error']} | {us['error']}" if (kr['error'] or us['error']) else None
    }


# ============================================================================
# Portfolio Management Functions (moved from menu/portfolio/portfolio.py)
# ============================================================================

import json
import os
from datetime import datetime, timezone

# Path to portfolio.json - relative to this module's location
PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'menu', 'portfolio', 'portfolio.json')

# Owner definitions
OWNERS = [
    {"id": "owner_01", "name": "곽성훈"},
    {"id": "owner_02", "name": "염인선"}
]


def _convert_kis_to_portfolio(kis_data: dict) -> dict:
    """
    Convert KIS API data to portfolio format.

    Args:
        kis_data: Output from _fetch_account_data()

    Returns:
        dict with 'holdings', 'accounts', 'asset_info', 'cash_holdings'
    """
    holdings = []
    accounts = {}
    asset_info = {}
    cash_holdings = []

    # KIS account (한국투자증권)
    kis_account_key = "한국투자증권_owner_01"
    accounts[kis_account_key] = {
        "name": "한국투자증권",
        "owner_id": "owner_01"
    }

    # Process domestic stocks (KR)
    for stock in kis_data.get('domestic_stocks', []):
        ticker = stock.get('ticker', '') or stock.get('symbol', '')
        qty = float(stock.get('qty', 0))
        avg_price = float(stock.get('avg_price', 0))
        name = stock.get('name', ticker)

        if qty <= 0:
            continue

        if ticker not in asset_info:
            asset_info[ticker] = {
                "name": name,
                "market": "KR",
                "asset_type": "Stock",
                "currency": "KRW"
            }

        holdings.append({
            "account_key": kis_account_key,
            "ticker": ticker,
            "name": name,
            "qty": qty,
            "avg_price": avg_price,
            "cur_price": float(stock.get('cur_price', 0))
        })

    # Process overseas stocks (US)
    for stock in kis_data.get('overseas_stocks', []):
        ticker = stock.get('symbol', '') or stock.get('ticker', '')
        qty = float(stock.get('qty', 0))
        avg_price = float(stock.get('avg_price', 0))
        name = stock.get('name', ticker)

        if qty <= 0:
            continue

        if ticker not in asset_info:
            asset_info[ticker] = {
                "name": name,
                "market": "US",
                "asset_type": "Stock",
                "currency": "USD"
            }

        holdings.append({
            "account_key": kis_account_key,
            "ticker": ticker,
            "name": name,
            "qty": qty,
            "avg_price": avg_price,
            "cur_price": float(stock.get('cur_price', 0))
        })

    # Add KRW orderable cash
    krw_orderable = kis_data.get('krw_orderable', 0)
    if krw_orderable:
        cash_holdings.append({
            "account_name": "한국투자증권",
            "amount": float(krw_orderable),
            "currency": "KRW"
        })

    # Add USD orderable cash
    overseas_asset = kis_data.get('overseas_asset', {})
    usd_orderable = float(overseas_asset.get('frcr_drwg_psbl_amt_1', 0))
    if usd_orderable > 0:
        cash_holdings.append({
            "account_name": "한국투자증권",
            "amount": usd_orderable,
            "currency": "USD"
        })

    return {
        "holdings": holdings,
        "accounts": accounts,
        "asset_info": asset_info,
        "cash_holdings": cash_holdings
    }


def get_portfolio() -> dict:
    """
    Update portfolio.json file by merging KIS API and GSheet data.

    Returns:
        dict: portfolio data
    """
    from display import add_alert
    from kis.gsheet import (
        connect_google_sheet, parse_worksheet_data, OWNERS
    )

    # Step 1: Fetch KIS API data
    add_alert("[KIS] Fetching KIS API data...", "INFO")

    kis_portfolio = None
    kis_raw_data = None
    try:
        kis_raw_data = _fetch_account_data()
        if kis_raw_data and not kis_raw_data.get('error'):
            kis_portfolio = _convert_kis_to_portfolio(kis_raw_data)
            kis_count = len(kis_portfolio.get('holdings', []))
            add_alert(f"[KIS] {kis_count} holdings loaded", "SUCCESS")
        else:
            add_alert("KIS: No data or error", "WARN")
    except Exception as e:
        add_alert(f"KIS skipped: {str(e)[:30]}", "WARN")

    # Step 2: Fetch GSheet data
    add_alert("[KIS] Fetching GSheet data...", "INFO")

    usd_sheet = connect_google_sheet('USD')
    krw_sheet = connect_google_sheet('KRW')

    gsheet_accounts = {}
    gsheet_holdings = []
    gsheet_asset_info = {}
    gsheet_cash = []
    gsheet_error = None  # Track GSheet connection errors

    if usd_sheet:
        usd_data = parse_worksheet_data(usd_sheet, "USD")
        gsheet_accounts.update(usd_data["accounts"])
        gsheet_holdings.extend(usd_data["holdings"])
        gsheet_asset_info.update(usd_data["asset_info"])
        gsheet_cash.extend(usd_data["cash_holdings"])

    if krw_sheet:
        krw_data = parse_worksheet_data(krw_sheet, "KRW")
        gsheet_accounts.update(krw_data["accounts"])
        gsheet_holdings.extend(krw_data["holdings"])
        gsheet_asset_info.update(krw_data["asset_info"])
        gsheet_cash.extend(krw_data["cash_holdings"])

    if not usd_sheet and not krw_sheet:
        add_alert("GSheet error: Failed to connect", "ERROR")
        gsheet_error = "Failed to connect to both USD and KRW sheets"
        if not kis_portfolio:
            return {"error": gsheet_error}
    elif not usd_sheet:
        gsheet_error = "Failed to connect to USD sheet"
        add_alert(f"GSheet warning: {gsheet_error}", "WARN")
    elif not krw_sheet:
        gsheet_error = "Failed to connect to KRW sheet"
        add_alert(f"GSheet warning: {gsheet_error}", "WARN")

    # Step 3: Merge data
    all_accounts = {}
    if kis_portfolio:
        all_accounts.update(kis_portfolio["accounts"])
    all_accounts.update(gsheet_accounts)

    # Assign account IDs
    account_list = []
    account_id_map = {}
    for idx, (key, acc) in enumerate(all_accounts.items(), start=1):
        acc_id = f"acc_{idx:02d}"
        account_id_map[key] = acc_id
        account_list.append({
            "id": acc_id,
            "owner_id": acc["owner_id"],
            "name": acc["name"]
        })

    # Merge asset info
    all_asset_info = {}
    if kis_portfolio:
        all_asset_info.update(kis_portfolio["asset_info"])
    all_asset_info.update(gsheet_asset_info)

    # Merge holdings with account IDs
    all_holdings = []
    if kis_portfolio:
        for h in kis_portfolio["holdings"]:
            acc_id = account_id_map.get(h["account_key"], "unknown")
            all_holdings.append({
                "account_id": acc_id,
                "ticker": h["ticker"],
                "name": h.get("name", h["ticker"]),
                "qty": h["qty"],
                "avg_price": h["avg_price"],
                "cur_price": h.get("cur_price", h["avg_price"])
            })

    for h in gsheet_holdings:
        acc_id = account_id_map.get(h["account_key"], "unknown")
        all_holdings.append({
            "account_id": acc_id,
            "ticker": h["ticker"],
            "name": h.get("name", h["ticker"]),
            "qty": h["qty"],
            "avg_price": h["avg_price"],
            "cur_price": h.get("cur_price", h["avg_price"])
        })

    # Merge cash holdings
    all_cash = []
    if kis_portfolio:
        all_cash.extend(kis_portfolio["cash_holdings"])
    all_cash.extend(gsheet_cash)

    # Build final portfolio
    metadata = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "exchange_rate": kis_raw_data.get('exchange_rate', None) if kis_raw_data else None
    }

    # Add error info if any data source failed
    if gsheet_error:
        metadata["gsheet_error"] = gsheet_error
    if kis_raw_data and kis_raw_data.get('error'):
        metadata["kis_error"] = kis_raw_data.get('error')

    portfolio = {
        "metadata": metadata,
        "owners": OWNERS,
        "asset_info": all_asset_info,
        "accounts": account_list,
        "holdings": all_holdings,
        "cash_holdings": all_cash
    }

    return portfolio
