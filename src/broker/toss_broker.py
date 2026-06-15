# -*- coding: utf-8 -*-
"""Application-owned facade for Toss strategy trading operations."""

import logging
from typing import Dict, Tuple

from kis.constants import ORDER_TYPE_US_LOC
from strategy.base import OrderSide, StrategyOrder
from toss.auth import load_access_token
from toss.create_order import create_order
from toss.get_buying_power import get_buying_power
from toss.get_holdings import _get_default_account_seq as get_default_account_seq


def _to_float(value, field_name: str) -> float:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Toss {field_name} is not numeric: {value!r}") from exc


def get_orderable_usd(symbol: str, order_price: float) -> float:
    """Return Toss USD cash buying power."""
    access_token = load_access_token()
    account_seq = get_default_account_seq(access_token)
    result = get_buying_power(
        account_seq=account_seq,
        currency="USD",
        access_token=access_token,
    )
    return _to_float(result.get("cashBuyingPower"), "cashBuyingPower")


def _order_payload(order: StrategyOrder) -> Dict[str, str]:
    side = "BUY" if order.side == OrderSide.BUY else "SELL"
    payload = {
        "symbol": order.symbol,
        "side": side,
        "quantity": str(order.quantity),
    }

    if order.price > 0:
        payload["order_type"] = "LIMIT"
        payload["price"] = str(order.price)
    else:
        payload["order_type"] = "MARKET"

    if order.order_type == ORDER_TYPE_US_LOC:
        if order.price <= 0:
            raise ValueError("Toss LOC order requires a positive limit price.")
        payload["order_type"] = "LIMIT"
        payload["time_in_force"] = "CLS"

    return payload


def place_order(order: StrategyOrder) -> Tuple[bool, str]:
    """Place a single stock order through Toss Invest."""
    try:
        access_token = load_access_token()
        account_seq = get_default_account_seq(access_token)
        create_order(
            account_seq=account_seq,
            access_token=access_token,
            **_order_payload(order),
        )
        return True, "Success"
    except Exception as exc:
        logging.error("[Toss] Strategy order failed for %s: %s", order.symbol, exc)
        return False, str(exc)
