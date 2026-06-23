"""토스증권 최근 체결 내역 조회 API 래퍼.

GET /api/v1/trades로 종목의 당일 최근 체결 내역을 조회한다.
조회 건수는 최대 50개이며 Rate Limits Group은 MARKET_DATA다.
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
from toss.get_orderbook import _get_payload
from toss.auth import load_access_token


def get_trades(
    *,
    symbol: str,
    access_token: str,
    count: int | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> list[dict[str, object]]:
    params: dict[str, object] = {"symbol": symbol.strip()}
    if count is not None:
        if count < 1 or count > 50:
            raise ValueError("count must be between 1 and 50.")
        params["count"] = count

    url = f"{base_url.rstrip('/')}/api/v1/trades?{parse.urlencode(params)}"
    return _get_payload(
        url=url,
        access_token=access_token,
        timeout=timeout,
        urlopen=urlopen,
        result_type=list,
        name="trades",
        group="MARKET_DATA",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest recent trades.")
    parser.add_argument("symbol", help="Symbol to query, e.g. 005930 or AAPL")
    parser.add_argument("--count", type=int, help="Number of trades, max 50")
    args = parser.parse_args()

    result = get_trades(symbol=args.symbol, count=args.count, access_token=load_access_token())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
