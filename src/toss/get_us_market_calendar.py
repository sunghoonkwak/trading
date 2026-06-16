"""토스증권 미국 장 운영 정보 조회 API 래퍼.

GET /api/v1/market-calendar/US로 미국 시장의 데이/프리/정규/애프터마켓 운영
시간을 조회한다. 기준일 주변 3영업일 정보를 KST 기준으로 반환하며
Rate Limits Group은 MARKET_INFO다.
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
from toss.get_exchange_rate import _get_result_object
from toss.auth import load_access_token


def get_us_market_calendar(
    *,
    access_token: str,
    date: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    query = f"?{parse.urlencode({'date': date})}" if date else ""
    url = f"{base_url.rstrip('/')}/api/v1/market-calendar/US{query}"
    return _get_result_object(url=url, access_token=access_token, timeout=timeout, urlopen=urlopen, name="US market-calendar")


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest US market calendar.")
    parser.add_argument("--date", help="Optional US-local date, YYYY-MM-DD")
    args = parser.parse_args()

    result = get_us_market_calendar(access_token=load_access_token(), date=args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
