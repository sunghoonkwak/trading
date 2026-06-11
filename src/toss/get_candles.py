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
from toss.get_prices import load_access_token


def get_candles(
    *,
    symbol: str,
    interval: str,
    access_token: str,
    count: int | None = None,
    before: str | None = None,
    adjusted: bool | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    if interval not in {"1m", "1d"}:
        raise ValueError("interval must be 1m or 1d.")

    params: dict[str, object] = {"symbol": symbol.strip(), "interval": interval}
    if count is not None:
        if count < 1 or count > 200:
            raise ValueError("count must be between 1 and 200.")
        params["count"] = count
    if before:
        params["before"] = before
    if adjusted is not None:
        params["adjusted"] = "true" if adjusted else "false"

    url = f"{base_url.rstrip('/')}/api/v1/candles?{parse.urlencode(params)}"
    return _get_payload(
        url=url,
        access_token=access_token,
        timeout=timeout,
        urlopen=urlopen,
        result_type=dict,
        name="candles",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest candles.")
    parser.add_argument("symbol", help="Symbol to query, e.g. 005930 or AAPL")
    parser.add_argument("--interval", required=True, choices=("1m", "1d"))
    parser.add_argument("--count", type=int, help="Number of candles, max 200")
    parser.add_argument("--before", help="Exclusive upper-bound ISO date-time")
    adjusted_group = parser.add_mutually_exclusive_group()
    adjusted_group.add_argument("--adjusted", dest="adjusted", action="store_true")
    adjusted_group.add_argument("--unadjusted", dest="adjusted", action="store_false")
    parser.set_defaults(adjusted=None)
    args = parser.parse_args()

    result = get_candles(
        symbol=args.symbol,
        interval=args.interval,
        count=args.count,
        before=args.before,
        adjusted=args.adjusted,
        access_token=load_access_token(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
