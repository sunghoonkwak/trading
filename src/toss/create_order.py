"""토스증권 주문 생성 API 래퍼.

POST /api/v1/orders로 국내/미국 주식 매수 또는 매도 주문을 생성한다.
수량(quantity) 또는 금액(orderAmount) 중 하나로 주문하며 계좌 헤더가 필요하다.
Rate Limits Group은 ORDER다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable
from urllib import request

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from toss.auth import DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from toss.client import request_json
from toss.get_holdings import _get_default_account_seq
from toss.auth import load_access_token


def create_order(
    *,
    account_seq: int,
    access_token: str,
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | None = None,
    price: str | None = None,
    order_amount: str | None = None,
    time_in_force: str | None = None,
    client_order_id: str | None = None,
    confirm_high_value_order: bool = False,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    body = {
        "symbol": symbol,
        "side": side.upper(),
        "orderType": order_type.upper(),
    }
    if quantity is not None:
        body["quantity"] = quantity
    if price is not None:
        body["price"] = price
    if order_amount is not None:
        body["orderAmount"] = order_amount
    if time_in_force is not None:
        body["timeInForce"] = time_in_force.upper()
    if client_order_id is not None:
        body["clientOrderId"] = client_order_id
    if confirm_high_value_order:
        body["confirmHighValueOrder"] = True

    return _post_order_action(
        url=f"{base_url.rstrip('/')}/api/v1/orders",
        account_seq=account_seq,
        access_token=access_token,
        body=body,
        timeout=timeout,
        urlopen=urlopen,
        action_name="create order",
    )


def _post_order_action(
    *,
    url: str,
    account_seq: int,
    access_token: str,
    body: dict[str, object],
    timeout: float,
    urlopen: Callable[..., object],
    action_name: str,
) -> dict[str, object]:
    api_request = request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Tossinvest-Account": str(account_seq),
            "Content-Type": "application/json",
        },
        method="POST",
    )

    payload = request_json(
        api_request,
        group="ORDER",
        action_name=action_name,
        timeout=timeout,
        urlopen=urlopen,
    )

    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"Toss {action_name} response does not contain result object.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Toss Invest order.")
    parser.add_argument("symbol")
    parser.add_argument("--account-seq", type=int, help="Toss accountSeq from get_accounts.py")
    parser.add_argument("--side", required=True, choices=("BUY", "SELL"))
    parser.add_argument("--order-type", required=True, choices=("LIMIT", "MARKET"))
    parser.add_argument("--quantity")
    parser.add_argument("--price")
    parser.add_argument("--order-amount")
    parser.add_argument("--time-in-force", choices=("DAY", "CLS"))
    parser.add_argument("--client-order-id")
    parser.add_argument("--confirm-high-value-order", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Actually submit the order")
    args = parser.parse_args()

    access_token = load_access_token()
    account_seq = args.account_seq or _get_default_account_seq(access_token)
    preview = {
        "accountSeq": account_seq,
        "symbol": args.symbol,
        "side": args.side,
        "orderType": args.order_type,
        "quantity": args.quantity,
        "price": args.price,
        "orderAmount": args.order_amount,
        "timeInForce": args.time_in_force,
        "clientOrderId": args.client_order_id,
    }
    if not args.execute:
        print(json.dumps({"dryRun": True, "request": preview}, ensure_ascii=False, indent=2))
        return

    result = create_order(
        account_seq=account_seq,
        access_token=access_token,
        symbol=args.symbol,
        side=args.side,
        order_type=args.order_type,
        quantity=args.quantity,
        price=args.price,
        order_amount=args.order_amount,
        time_in_force=args.time_in_force,
        client_order_id=args.client_order_id,
        confirm_high_value_order=args.confirm_high_value_order,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
