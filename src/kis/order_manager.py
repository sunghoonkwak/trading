# -*- coding: utf-8 -*-
"""
KIS Order Manager Module

Handles searching, canceling, and correcting open orders.
"""
import logging
import pandas as pd
from typing import Tuple, Dict, Optional, Any

from kis.kis_api import kis_auth as ka
from kis.kis_api.domestic_stock.order_rvsecncl.order_rvsecncl import order_rvsecncl
from kis.kis_api.domestic_stock.inquire_psbl_rvsecncl.inquire_psbl_rvsecncl import inquire_psbl_rvsecncl
from kis.kis_api.overseas_stock.order_rvsecncl.order_rvsecncl import order_rvsecncl as order_rvsecncl_overseas
from kis.kis_api.overseas_stock.inquire_nccs.inquire_nccs import inquire_nccs as inquire_nccs_overseas

class OrderManager:
    """Encapsulates KIS order management operations."""

    @staticmethod
    def fetch_open_orders() -> Tuple[pd.DataFrame, int, int]:
        """Fetch open orders from all markets."""
        cano = ka.getTREnv().my_acct
        prod = ka.getTREnv().my_prod

        # 1. US Market
        try:
            df_us = inquire_nccs_overseas(cano=cano, acnt_prdt_cd=prod, ovrs_excg_cd="NASD", sort_sqn="DS", FK200="", NK200="")
            if not df_us.empty:
                df_us['_market'] = 'US'
        except Exception as e:
            logging.error(f"[OrderManager] US order fetch failed: {e}")
            df_us = pd.DataFrame()

        # 2. KR Market
        try:
            df_kr = inquire_psbl_rvsecncl(cano=cano, acnt_prdt_cd=prod, inqr_dvsn_1="0", inqr_dvsn_2="0")
            if not df_kr.empty:
                df_kr['_market'] = 'KR'
        except Exception as e:
            logging.error(f"[OrderManager] KR order fetch failed: {e}")
            df_kr = pd.DataFrame()

        if df_us.empty and df_kr.empty:
            return pd.DataFrame(), 0, 0

        combined = pd.concat([df_us, df_kr], ignore_index=True)
        return combined, len(df_us), len(df_kr)

    @staticmethod
    def execute_action(market: str, action_type: str, order_data: Dict[str, Any], new_price: Optional[str] = None) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """Execute cancel (2) or correction (1) for an order."""
        cano = ka.getTREnv().my_acct
        prod = ka.getTREnv().my_prod
        t_ord = {k.lower(): v for k, v in order_data.items()}
        order_no = t_ord.get('odno', 'Unknown')
        action_name = "CANCEL" if action_type == '2' else "CORRECT"

        logging.info(f"[OrderManager] Requesting {action_name} for order {order_no} ({market})")

        try:
            if market == "KR":
                res_df, msg = order_rvsecncl(
                    env_dv="real", cano=cano, acnt_prdt_cd=prod,
                    krx_fwdg_ord_orgno=t_ord.get('ord_gno_brno', t_ord.get('krx_fwdg_ord_orgno', '')),
                    orgn_odno=order_no,
                    ord_dvsn=t_ord.get('ord_dvsn_cd', t_ord.get('ord_dvsn', '00')),
                    rvse_cncl_dvsn_cd="02" if action_type == '2' else "01",
                    ord_qty=t_ord.get('psbl_qty'),
                    ord_unpr=new_price if action_type == '1' else "0",
                    qty_all_ord_yn="Y", excg_id_dvsn_cd=t_ord.get('excg_id_dvsn_cd', 'KRX')
                )
            else:
                qty = t_ord.get('nccs_qty', t_ord.get('ft_ord_qty4', t_ord.get('ord_qty', 0)))
                res_df, msg = order_rvsecncl_overseas(
                    cano=cano, acnt_prdt_cd=prod, ovrs_excg_cd=t_ord.get('ovrs_excg_cd', 'NASD'),
                    pdno=t_ord.get('pdno'), orgn_odno=order_no,
                    rvse_cncl_dvsn_cd="02" if action_type == '2' else "01",
                    ord_qty=str(qty),
                    ovrs_ord_unpr=new_price if action_type == '1' else "0",
                    mgco_aptm_odno="", ord_svr_dvsn_cd="0", env_dv="real"
                )
            
            if res_df is not None:
                logging.info(f"[OrderManager] {action_name} success: {order_no} | Msg: {msg}")
            else:
                logging.warning(f"[OrderManager] {action_name} failed: {order_no} | Msg: {msg}")
            
            return res_df, msg
            
        except Exception as e:
            logging.error(f"[OrderManager] {action_name} exception: {order_no} | Error: {e}")
            return None, str(e)
