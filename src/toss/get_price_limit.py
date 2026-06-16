"""토스증권 상/하한가 조회 API 래퍼.

GET /api/v1/price-limits로 종목의 당일 상한가와 하한가를 조회한다.
계좌 정보 없이 액세스 토큰만으로 호출하며 Rate Limits Group은 MARKET_DATA다.
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


def get_price_limit(
    *,
    symbol: str,
    access_token: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    query = parse.urlencode({"symbol": symbol.strip()})
    url = f"{base_url.rstrip('/')}/api/v1/price-limits?{query}"
    return _get_payload(
        url=url,
        access_token=access_token,
        timeout=timeout,
        urlopen=urlopen,
        result_type=dict,
        name="price-limits",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest price limits.")
    parser.add_argument("symbol", help="Symbol to query, e.g. 005930 or AAPL")
    args = parser.parse_args()

    result = get_price_limit(symbol=args.symbol, access_token=load_access_token())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
