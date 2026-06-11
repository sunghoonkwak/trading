from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Sequence
from urllib import error, parse, request

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from toss.auth import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, TOKEN_DIR, load_latest_token


def load_access_token(token_dir=TOKEN_DIR) -> str:
    token_payload = load_latest_token(token_dir)
    if not token_payload:
        raise RuntimeError("No saved Toss token found. Run src/toss/auth.py first.")

    access_token = token_payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("Saved Toss token file does not contain access_token.")
    return access_token


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

    try:
        with urlopen(prices_request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Toss prices request failed: HTTP {exc.code} {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Toss prices request failed: {exc.reason}") from exc

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
