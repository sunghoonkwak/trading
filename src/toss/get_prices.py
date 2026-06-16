"""토스증권 현재가 조회 API 래퍼.

GET /api/v1/prices로 하나 이상의 종목 현재가 정보를 조회한다.
symbols를 콤마로 구분해 최대 200개까지 요청할 수 있으며 Rate Limits Group은
MARKET_DATA다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Sequence
from urllib import parse, request

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from toss.auth import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, load_access_token
from toss.client import request_json


def get_prices(
    symbols: Sequence[str],
    *,
    access_token: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> list[dict[str, object]]:
    cleaned_symbols = [symbol.strip() for symbol in symbols if symbol.strip()]
    if not cleaned_symbols:
        raise ValueError("At least one symbol is required.")
    if len(cleaned_symbols) > 200:
        raise ValueError("Toss prices API supports up to 200 symbols per request.")

    query = parse.urlencode({"symbols": ",".join(cleaned_symbols)})
    prices_url = f"{base_url.rstrip('/')}/api/v1/prices?{query}"
    prices_request = request.Request(
        prices_url,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )

    payload = request_json(
        prices_request,
        group="MARKET_DATA",
        action_name="prices",
        timeout=timeout,
        urlopen=urlopen,
    )

    result = payload.get("result")
    if not isinstance(result, list):
        raise RuntimeError("Toss prices response does not contain result list.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest current prices.")
    parser.add_argument(
        "symbols",
        nargs="+",
        help="Symbols to query, e.g. 005930 AAPL or 005930,AAPL",
    )
    args = parser.parse_args()

    symbols: list[str] = []
    for value in args.symbols:
        symbols.extend(value.split(","))

    prices = get_prices(symbols, access_token=load_access_token())
    print(json.dumps(prices, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
