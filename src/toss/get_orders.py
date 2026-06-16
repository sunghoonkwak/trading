"""토스증권 주문 목록 조회 API 래퍼.

GET /api/v1/orders로 진행 중(OPEN) 또는 종료된(CLOSED) 주문 목록을 조회한다.
symbol과 기간으로 필터링할 수 있으며 계좌 헤더가 필요하다.
Rate Limits Group은 ORDER_HISTORY다.
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
from toss.account_cache import get_default_account_seq
from toss.auth import load_access_token


def get_orders(
    *,
    account_seq: int,
    status: str,
    access_token: str,
    symbol: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    status = status.upper()
    if status not in {"OPEN", "CLOSED"}:
        raise ValueError("status must be OPEN or CLOSED.")

    params: dict[str, object] = {"status": status}
    if symbol:
        params["symbol"] = symbol
    if date_from:
        params["from"] = date_from
    if date_to:
        params["to"] = date_to
    if cursor:
        params["cursor"] = cursor
    if limit is not None:
        params["limit"] = limit

    query = parse.urlencode(params)
    url = f"{base_url.rstrip('/')}/api/v1/orders?{query}"
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
        action_name="orders",
        timeout=timeout,
        urlopen=urlopen,
    )

    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Toss orders response does not contain result object.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest orders.")
    parser.add_argument("--account-seq", type=int, help="Toss accountSeq from get_accounts.py")
    parser.add_argument("--status", default="OPEN", choices=("OPEN", "CLOSED"), help="Order lifecycle group")
    parser.add_argument("--symbol", help="Optional symbol filter, e.g. 005930 or AAPL")
    parser.add_argument("--from", dest="date_from", help="Start date inclusive, YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="End date inclusive, YYYY-MM-DD")
    parser.add_argument("--cursor", help="Pagination cursor")
    parser.add_argument("--limit", type=int, help="Page size, 1-100")
    args = parser.parse_args()

    access_token = load_access_token()
    account_seq = args.account_seq or get_default_account_seq(access_token)
    result = get_orders(
        account_seq=account_seq,
        status=args.status,
        access_token=access_token,
        symbol=args.symbol,
        date_from=args.date_from,
        date_to=args.date_to,
        cursor=args.cursor,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
