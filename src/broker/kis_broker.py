# -*- coding: utf-8 -*-
"""Application-owned facade for KIS trading operations."""

import logging
from typing import Tuple

import requests

from core import trading_config
from kis.constants import EXCHANGE_CODE_MAP, ORDER_TYPE_US_LIMIT, ORDER_TYPE_US_LOC
from strategy.base import OrderSide, StrategyOrder
from strategy.constants import ORDER_TYPE_LIMIT, ORDER_TYPE_LOC

ka = None
inquire_psamount = None
order_overseas_stock = None

_ORDER_TYPE_TO_KIS = {
    ORDER_TYPE_LIMIT: ORDER_TYPE_US_LIMIT,
    ORDER_TYPE_LOC: ORDER_TYPE_US_LOC,
}


def _get_kis_auth():
    global ka
    if ka is None:
        from kis.kis_api import kis_auth

        ka = kis_auth
    return ka


def _get_inquire_psamount():
    global inquire_psamount
    if inquire_psamount is None:
        from kis.kis_api.overseas_stock.inquire_psamount.inquire_psamount import (
            inquire_psamount as imported_inquire_psamount,
        )

        inquire_psamount = imported_inquire_psamount
    return inquire_psamount


def _get_order_overseas_stock():
    global order_overseas_stock
    if order_overseas_stock is None:
        from kis.kis_api.overseas_stock.order.order import (
            order as imported_order_overseas_stock,
        )

        order_overseas_stock = imported_order_overseas_stock
    return order_overseas_stock


def get_orderable_usd(symbol: str, order_price: float) -> float:
    """Return KIS overseas buying power for a representative USD buy."""
    stock_info = trading_config.get_stock_info(symbol)
    market = stock_info.get("market", "NASD")
    ovrs_excg_cd = EXCHANGE_CODE_MAP.get(market, market)
    trenv = _get_kis_auth().getTREnv()

    result = _get_inquire_psamount()(
        cano=trenv.my_acct,
        acnt_prdt_cd=trenv.my_prod,
        ovrs_excg_cd=ovrs_excg_cd,
        ovrs_ord_unpr=str(order_price),
        item_cd=symbol,
        env_dv="real",
    )
    if result is None or result.empty or "ovrs_ord_psbl_amt" not in result:
        raise RuntimeError("KIS did not return overseas orderable USD.")
    return float(result.iloc[0]["ovrs_ord_psbl_amt"])


def place_overseas_order(order: StrategyOrder) -> Tuple[bool, str]:
    """Place a single overseas stock order through KIS."""
    try:
        trenv = _get_kis_auth().getTREnv()
        ord_dv = "buy" if order.side == OrderSide.BUY else "sell"

        exec_price = order.price
        exec_type = _ORDER_TYPE_TO_KIS.get(order.order_type, order.order_type)
        if order.side == OrderSide.SELL and order.price == 0:
            exec_price = 0.01
            exec_type = ORDER_TYPE_US_LIMIT

        stock_info = trading_config.get_stock_info(order.symbol)
        market = stock_info.get("market", "NASD")
        ovrs_excg_cd = EXCHANGE_CODE_MAP.get(market, market)

        res, err = _get_order_overseas_stock()(
            cano=trenv.my_acct,
            acnt_prdt_cd=trenv.my_prod,
            ovrs_excg_cd=ovrs_excg_cd,
            pdno=order.symbol,
            ord_qty=str(order.quantity),
            ovrs_ord_unpr=str(exec_price),
            ord_dv=ord_dv,
            ctac_tlno="",
            mgco_aptm_odno="",
            ord_svr_dvsn_cd="0",
            ord_dvsn=exec_type,
            env_dv="real",
        )

        if res is not None and not res.empty:
            return True, "Success"
        return False, str(err)
    except requests.exceptions.Timeout:
        error_msg = f"[API Timeout] execution timed out for {order.symbol}"
        logging.error(error_msg)
        return False, error_msg
    except Exception as e:
        return False, str(e)
