from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable
from urllib import parse, request

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from toss.auth import DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from toss.create_order import _post_order_action
from toss.get_holdings import _get_default_account_seq
from toss.auth import load_access_token


def modify_order(
    *,
    order_id: str,
    account_seq: int,
    access_token: str,
    order_type: str,
    quantity: str | None = None,
    price: str | None = None,
    confirm_high_value_order: bool = False,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    body: dict[str, object] = {"orderType": order_type.upper()}
    if quantity is not None:
        body["quantity"] = quantity
    if price is not None:
        body["price"] = price
    if confirm_high_value_order:
        body["confirmHighValueOrder"] = True

    encoded_order_id = parse.quote(order_id.strip(), safe="")
    return _post_order_action(
        url=f"{base_url.rstrip('/')}/api/v1/orders/{encoded_order_id}/modify",
        account_seq=account_seq,
        access_token=access_token,
        body=body,
        timeout=timeout,
        urlopen=urlopen,
        action_name="modify order",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Modify a Toss Invest order.")
    parser.add_argument("order_id")
    parser.add_argument("--account-seq", type=int, help="Toss accountSeq from get_accounts.py")
    parser.add_argument("--order-type", required=True, choices=("LIMIT", "MARKET"))
    parser.add_argument("--quantity")
    parser.add_argument("--price")
    parser.add_argument("--confirm-high-value-order", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Actually submit the modification")
    args = parser.parse_args()

    access_token = load_access_token()
    account_seq = args.account_seq or _get_default_account_seq(access_token)
    preview = {
        "accountSeq": account_seq,
        "orderId": args.order_id,
        "orderType": args.order_type,
        "quantity": args.quantity,
        "price": args.price,
    }
    if not args.execute:
        print(json.dumps({"dryRun": True, "request": preview}, ensure_ascii=False, indent=2))
        return

    result = modify_order(
        order_id=args.order_id,
        account_seq=account_seq,
        access_token=access_token,
        order_type=args.order_type,
        quantity=args.quantity,
        price=args.price,
        confirm_high_value_order=args.confirm_high_value_order,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
