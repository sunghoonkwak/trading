"""Toss Invest conditional-order API helpers.

These helpers submit and manage broker-hosted conditional orders.  They are not
wired into strategy execution; callers must explicitly choose to create,
modify, or cancel an order.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Callable
from urllib import parse, request

from infrastructure.toss.auth import DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from infrastructure.toss.client import request_json

_ORDER_TYPES = {"LIMIT", "MARKET"}
_CONDITIONAL_TYPES = {"SINGLE", "OCO", "OTO"}


def create_conditional_order(
    *,
    account_seq: int,
    access_token: str,
    symbol: str,
    conditional_type: str,
    quantity: str,
    order_type: str,
    expire_date: str,
    first: Mapping[str, object],
    second: Mapping[str, object] | None = None,
    client_order_id: str | None = None,
    confirm_high_value_order: bool = False,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    body = _conditional_order_body(
        conditional_type=conditional_type,
        quantity=quantity,
        order_type=order_type,
        expire_date=expire_date,
        first=first,
        second=second,
    )
    body["symbol"] = symbol.strip()
    if not body["symbol"]:
        raise ValueError("symbol is required.")
    if client_order_id is not None:
        body["clientOrderId"] = client_order_id
    if confirm_high_value_order:
        body["confirmHighValueOrder"] = True
    return _request_conditional_result(
        method="POST",
        path="/api/v1/conditional-orders",
        account_seq=account_seq,
        access_token=access_token,
        body=body,
        base_url=base_url,
        timeout=timeout,
        urlopen=urlopen,
        action_name="create conditional order",
    )


def get_conditional_orders(
    *,
    account_seq: int,
    access_token: str,
    status: str,
    symbol: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    status = status.upper()
    if status not in {"OPEN", "CLOSED"}:
        raise ValueError("status must be OPEN or CLOSED.")
    if limit is not None and not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100.")
    params: dict[str, object] = {"status": status}
    if symbol:
        params["symbol"] = symbol.strip()
    if cursor:
        params["cursor"] = cursor
    if limit is not None:
        params["limit"] = limit
    return _request_conditional_result(
        method="GET",
        path=f"/api/v1/conditional-orders?{parse.urlencode(params)}",
        account_seq=account_seq,
        access_token=access_token,
        base_url=base_url,
        timeout=timeout,
        urlopen=urlopen,
        action_name="conditional orders",
    )


def get_conditional_order(
    *,
    conditional_order_id: str,
    account_seq: int,
    access_token: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    return _request_conditional_result(
        method="GET",
        path=_conditional_order_path(conditional_order_id),
        account_seq=account_seq,
        access_token=access_token,
        base_url=base_url,
        timeout=timeout,
        urlopen=urlopen,
        action_name="conditional order",
    )


def cancel_conditional_order(
    *,
    conditional_order_id: str,
    account_seq: int,
    access_token: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> None:
    _request_conditional_result(
        method="DELETE",
        path=_conditional_order_path(conditional_order_id),
        account_seq=account_seq,
        access_token=access_token,
        base_url=base_url,
        timeout=timeout,
        urlopen=urlopen,
        action_name="cancel conditional order",
        expect_result=False,
    )


def modify_conditional_order(
    *,
    conditional_order_id: str,
    account_seq: int,
    access_token: str,
    conditional_type: str,
    quantity: str,
    order_type: str,
    expire_date: str,
    first: Mapping[str, object],
    second: Mapping[str, object] | None = None,
    confirm_high_value_order: bool = False,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    body = _conditional_order_body(
        conditional_type=conditional_type,
        quantity=quantity,
        order_type=order_type,
        expire_date=expire_date,
        first=first,
        second=second,
    )
    if confirm_high_value_order:
        body["confirmHighValueOrder"] = True
    return _request_conditional_result(
        method="POST",
        path=f"{_conditional_order_path(conditional_order_id)}/modify",
        account_seq=account_seq,
        access_token=access_token,
        body=body,
        base_url=base_url,
        timeout=timeout,
        urlopen=urlopen,
        action_name="modify conditional order",
    )


def _conditional_order_body(
    *,
    conditional_type: str,
    quantity: str,
    order_type: str,
    expire_date: str,
    first: Mapping[str, object],
    second: Mapping[str, object] | None,
) -> dict[str, object]:
    conditional_type = conditional_type.upper()
    order_type = order_type.upper()
    if conditional_type not in _CONDITIONAL_TYPES:
        raise ValueError("conditional_type must be SINGLE, OCO, or OTO.")
    if order_type not in _ORDER_TYPES:
        raise ValueError("order_type must be LIMIT or MARKET.")
    if not quantity.strip() or not expire_date.strip():
        raise ValueError("quantity and expire_date are required.")
    if conditional_type == "SINGLE" and second is not None:
        raise ValueError("SINGLE conditional orders cannot include second.")
    if conditional_type != "SINGLE" and second is None:
        raise ValueError("OCO and OTO conditional orders require second.")
    if conditional_type != "SINGLE" and order_type != "LIMIT":
        raise ValueError("OCO and OTO conditional orders require LIMIT order_type.")

    normalized_first = _normalize_condition(first, order_type=order_type, name="first")
    body: dict[str, object] = {
        "type": conditional_type,
        "quantity": quantity,
        "orderType": order_type,
        "expireDate": expire_date,
        "first": normalized_first,
    }
    if second is not None:
        normalized_second = _normalize_condition(second, order_type=order_type, name="second")
        body["second"] = normalized_second
        if conditional_type == "OCO" and (
            normalized_first["orderSide"] != "SELL" or normalized_second["orderSide"] != "SELL"
        ):
            raise ValueError("OCO conditions must both be SELL orders.")
        if conditional_type == "OTO" and (
            normalized_first["orderSide"] != "BUY" or normalized_second["orderSide"] != "SELL"
        ):
            raise ValueError("OTO conditions must be BUY then SELL.")
    return body


def _normalize_condition(
    condition: Mapping[str, object],
    *,
    order_type: str,
    name: str,
) -> dict[str, object]:
    side = str(condition.get("orderSide", "")).upper()
    trigger_price = condition.get("triggerPrice")
    order_price = condition.get("orderPrice")
    if side not in {"BUY", "SELL"} or trigger_price in {None, ""}:
        raise ValueError(f"{name} requires BUY or SELL orderSide and triggerPrice.")
    if order_type == "LIMIT" and order_price in {None, ""}:
        raise ValueError(f"{name}.orderPrice is required for LIMIT orders.")
    if order_type == "MARKET" and order_price not in {None, ""}:
        raise ValueError(f"{name}.orderPrice is not allowed for MARKET orders.")
    normalized: dict[str, object] = {"orderSide": side, "triggerPrice": trigger_price}
    if order_price not in {None, ""}:
        normalized["orderPrice"] = order_price
    return normalized


def _conditional_order_path(conditional_order_id: str) -> str:
    identifier = conditional_order_id.strip()
    if not identifier:
        raise ValueError("conditional_order_id is required.")
    return f"/api/v1/conditional-orders/{parse.quote(identifier, safe='')}"


def _request_conditional_result(
    *,
    method: str,
    path: str,
    account_seq: int,
    access_token: str,
    base_url: str,
    timeout: float,
    urlopen: Callable[..., object],
    action_name: str,
    body: dict[str, object] | None = None,
    expect_result: bool = True,
) -> dict[str, object]:
    api_request = request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Tossinvest-Account": str(account_seq),
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
        method=method,
    )
    payload = request_json(
        api_request,
        group=("CONDITIONAL_ORDER" if method != "GET" else "CONDITIONAL_ORDER_HISTORY"),
        action_name=action_name,
        timeout=timeout,
        urlopen=urlopen,
    )
    if not expect_result:
        return {}
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"Toss {action_name} response does not contain result object.")
    return result
