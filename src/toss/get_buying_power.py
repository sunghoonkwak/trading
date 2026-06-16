"""토스증권 매수 가능 금액 조회 API 래퍼.

GET /api/v1/buying-power로 특정 종목 매수 주문에 사용할 수 있는 현금 기반
매수 가능 금액을 조회한다. 계좌 헤더 X-Tossinvest-Account가 필요하며
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


def get_buying_power(
    *,
    account_seq: int,
    currency: str,
    access_token: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    currency = currency.upper()
    if currency not in {"KRW", "USD"}:
        raise ValueError("currency must be KRW or USD.")

    query = parse.urlencode({"currency": currency})
    url = f"{base_url.rstrip('/')}/api/v1/buying-power?{query}"
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
        action_name="buying-power",
        timeout=timeout,
        urlopen=urlopen,
    )

    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Toss buying-power response does not contain result object.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest buying power.")
    parser.add_argument("--account-seq", type=int, help="Toss accountSeq from get_accounts.py")
    parser.add_argument("--currency", required=True, choices=("KRW", "USD"), help="Currency to query")
    args = parser.parse_args()

    access_token = load_access_token()
    account_seq = args.account_seq or get_default_account_seq(access_token)
    result = get_buying_power(
        account_seq=account_seq,
        currency=args.currency,
        access_token=access_token,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
