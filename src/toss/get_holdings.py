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
from toss.client import request_json
from toss.get_accounts import get_accounts
from toss.auth import load_access_token


def get_holdings(
    *,
    account_seq: int,
    access_token: str,
    symbol: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    query = f"?{parse.urlencode({'symbol': symbol})}" if symbol else ""
    holdings_url = f"{base_url.rstrip('/')}/api/v1/holdings{query}"
    holdings_request = request.Request(
        holdings_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Tossinvest-Account": str(account_seq),
        },
        method="GET",
    )

    payload = request_json(
        holdings_request,
        group="ASSET",
        action_name="holdings",
        timeout=timeout,
        urlopen=urlopen,
    )

    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Toss holdings response does not contain result object.")
    return result


def _get_default_account_seq(access_token: str) -> int:
    accounts = get_accounts(access_token=access_token)
    if not accounts:
        raise RuntimeError("No Toss account found. Cannot query holdings.")

    account_seq = accounts[0].get("accountSeq")
    if not isinstance(account_seq, int):
        raise RuntimeError("First Toss account does not contain integer accountSeq.")
    return account_seq


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest holdings.")
    parser.add_argument("--account-seq", type=int, help="Toss accountSeq from get_accounts.py")
    parser.add_argument("--symbol", help="Optional symbol filter, e.g. 005930 or AAPL")
    args = parser.parse_args()

    access_token = load_access_token()
    account_seq = args.account_seq or _get_default_account_seq(access_token)
    holdings = get_holdings(
        account_seq=account_seq,
        access_token=access_token,
        symbol=args.symbol,
    )
    print(json.dumps(holdings, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
