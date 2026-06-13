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
from toss.get_holdings import _get_default_account_seq
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

    try:
        with urlopen(api_request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Toss sellable-quantity request failed: HTTP {exc.code} {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Toss sellable-quantity request failed: {exc.reason}") from exc

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
    account_seq = args.account_seq or _get_default_account_seq(access_token)
    result = get_sellable_quantity(
        account_seq=account_seq,
        symbol=args.symbol,
        access_token=access_token,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
