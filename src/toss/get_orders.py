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
from toss.get_prices import load_access_token


def get_orders(
    *,
    account_seq: int,
    status: str,
    access_token: str,
    symbol: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    status = status.upper()
    if status not in {"OPEN", "CLOSED"}:
        raise ValueError("status must be OPEN or CLOSED.")

    params: dict[str, object] = {"status": status}
    if symbol:
        params["symbol"] = symbol
    if date_from:
        params["from"] = date_from
    if date_to:
        params["to"] = date_to
    if cursor:
        params["cursor"] = cursor
    if limit is not None:
        params["limit"] = limit

    query = parse.urlencode(params)
    url = f"{base_url.rstrip('/')}/api/v1/orders?{query}"
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
        raise RuntimeError(f"Toss orders request failed: HTTP {exc.code} {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Toss orders request failed: {exc.reason}") from exc

    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Toss orders response does not contain result object.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest orders.")
    parser.add_argument("--account-seq", type=int, help="Toss accountSeq from get_accounts.py")
    parser.add_argument("--status", default="OPEN", choices=("OPEN", "CLOSED"), help="Order lifecycle group")
    parser.add_argument("--symbol", help="Optional symbol filter, e.g. 005930 or AAPL")
    parser.add_argument("--from", dest="date_from", help="Start date inclusive, YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="End date inclusive, YYYY-MM-DD")
    parser.add_argument("--cursor", help="Pagination cursor")
    parser.add_argument("--limit", type=int, help="Page size, 1-100")
    args = parser.parse_args()

    access_token = load_access_token()
    account_seq = args.account_seq or _get_default_account_seq(access_token)
    result = get_orders(
        account_seq=account_seq,
        status=args.status,
        access_token=access_token,
        symbol=args.symbol,
        date_from=args.date_from,
        date_to=args.date_to,
        cursor=args.cursor,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
