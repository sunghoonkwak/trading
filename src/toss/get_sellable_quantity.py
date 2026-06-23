"""토스증권 판매 가능 수량 조회 API 래퍼.

GET /api/v1/sellable-quantity로 특정 종목의 매도 가능 수량을 조회한다.
주문 전 최대 매도 가능 수량 확인에 쓰며 계좌 헤더가 필요하다.
Rate Limits Group은 ORDER_INFO다.
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


def get_sellable_quantity(
    *,
    account_seq: int,
    symbol: str,
    access_token: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    symbol = symbol.strip()
    if not symbol:
        raise ValueError("symbol is required.")

    query = parse.urlencode({"symbol": symbol})
    url = f"{base_url.rstrip('/')}/api/v1/sellable-quantity?{query}"
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
        group="ORDER_INFO",
        action_name="sellable-quantity",
        timeout=timeout,
        urlopen=urlopen,
    )

    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Toss sellable-quantity response does not contain result object.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest sellable quantity.")
    parser.add_argument("symbol", help="Symbol to query, e.g. 005930 or AAPL")
    parser.add_argument("--account-seq", type=int, help="Toss accountSeq from get_accounts.py")
    args = parser.parse_args()

    access_token = load_access_token()
    account_seq = args.account_seq or get_default_account_seq(access_token)
    result = get_sellable_quantity(
        account_seq=account_seq,
        symbol=args.symbol,
        access_token=access_token,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
