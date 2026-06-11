from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable
from urllib import error, parse, request

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from toss.auth import DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from toss.get_prices import load_access_token


def _get_payload(
    *,
    url: str,
    access_token: str,
    timeout: float,
    urlopen: Callable[..., object],
    result_type: type,
    name: str,
) -> object:
    api_request = request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    try:
        with urlopen(api_request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Toss {name} request failed: HTTP {exc.code} {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Toss {name} request failed: {exc.reason}") from exc

    result = payload.get("result")
    if not isinstance(result, result_type):
        raise RuntimeError(f"Toss {name} response has unexpected result type.")
    return result


def get_orderbook(
    *,
    symbol: str,
    access_token: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    query = parse.urlencode({"symbol": symbol.strip()})
    url = f"{base_url.rstrip('/')}/api/v1/orderbook?{query}"
    return _get_payload(
        url=url,
        access_token=access_token,
        timeout=timeout,
        urlopen=urlopen,
        result_type=dict,
        name="orderbook",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest orderbook.")
    parser.add_argument("symbol", help="Symbol to query, e.g. 005930 or AAPL")
    args = parser.parse_args()

    result = get_orderbook(symbol=args.symbol, access_token=load_access_token())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
