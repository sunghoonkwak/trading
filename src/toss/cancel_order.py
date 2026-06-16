"""토스증권 주문 취소 API 래퍼.

POST /api/v1/orders/{orderId}/cancel로 기존 미체결 주문 취소를 요청한다.
계좌 헤더 X-Tossinvest-Account가 필요하며 Rate Limits Group은 ORDER다.
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
from toss.create_order import _post_order_action
from toss.get_holdings import _get_default_account_seq
from toss.auth import load_access_token


def cancel_order(
    *,
    order_id: str,
    account_seq: int,
    access_token: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    encoded_order_id = parse.quote(order_id.strip(), safe="")
    return _post_order_action(
        url=f"{base_url.rstrip('/')}/api/v1/orders/{encoded_order_id}/cancel",
        account_seq=account_seq,
        access_token=access_token,
        body={},
        timeout=timeout,
        urlopen=urlopen,
        action_name="cancel order",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Cancel a Toss Invest order.")
    parser.add_argument("order_id")
    parser.add_argument("--account-seq", type=int, help="Toss accountSeq from get_accounts.py")
    parser.add_argument("--execute", action="store_true", help="Actually submit the cancellation")
    args = parser.parse_args()

    access_token = load_access_token()
    account_seq = args.account_seq or _get_default_account_seq(access_token)
    preview = {"accountSeq": account_seq, "orderId": args.order_id}
    if not args.execute:
        print(json.dumps({"dryRun": True, "request": preview}, ensure_ascii=False, indent=2))
        return

    result = cancel_order(
        order_id=args.order_id,
        account_seq=account_seq,
        access_token=access_token,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
