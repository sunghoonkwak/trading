"""토스증권 주문 상세 조회 API 래퍼.

GET /api/v1/orders/{orderId}로 특정 주문의 상태, 체결 내역, 수수료/세금 등
주문 단위 상세 정보를 조회한다. 계좌 헤더가 필요하며 Rate Limits Group은
ORDER_HISTORY다.
"""

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
from toss.client import request_json
from toss.get_holdings import _get_default_account_seq
from toss.auth import load_access_token


def get_order(
    *,
    order_id: str,
    account_seq: int,
    access_token: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    order_id = order_id.strip()
    if not order_id:
        raise ValueError("order_id is required.")

    encoded_order_id = parse.quote(order_id, safe="")
    url = f"{base_url.rstrip('/')}/api/v1/orders/{encoded_order_id}"
    api_request = request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Tossinvest-Account": str(account_seq),
        },
        method="GET",
    )

    payload = request_json(
        api_request,
        group="ORDER_HISTORY",
        action_name="order",
        timeout=timeout,
        urlopen=urlopen,
    )

    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Toss order response does not contain result object.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest order detail.")
    parser.add_argument("order_id", help="Order ID from get_orders.py")
    parser.add_argument("--account-seq", type=int, help="Toss accountSeq from get_accounts.py")
    args = parser.parse_args()

    access_token = load_access_token()
    account_seq = args.account_seq or _get_default_account_seq(access_token)
    result = get_order(
        order_id=args.order_id,
        account_seq=account_seq,
        access_token=access_token,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
