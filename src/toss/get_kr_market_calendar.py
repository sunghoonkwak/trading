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
from toss.get_prices import load_access_token


def get_kr_market_calendar(
    *,
    access_token: str,
    date: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    query = f"?{parse.urlencode({'date': date})}" if date else ""
    url = f"{base_url.rstrip('/')}/api/v1/market-calendar/KR{query}"
    return _get_result_object(url=url, access_token=access_token, timeout=timeout, urlopen=urlopen, name="KR market-calendar")


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest KR market calendar.")
    parser.add_argument("--date", help="Optional date, YYYY-MM-DD")
    args = parser.parse_args()

    result = get_kr_market_calendar(access_token=load_access_token(), date=args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
