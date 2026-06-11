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


def get_order(
    *,
    order_id: str,
    account_seq: int,
    access_token: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    order_id = order_id.strip()
    if not order_id:
        raise ValueError("order_id is required.")

    encoded_order_id = parse.quote(order_id, safe="")
    url = f"{base_url.rstrip('/')}/api/v1/orders/{encoded_order_id}"
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
        raise RuntimeError(f"Toss order request failed: HTTP {exc.code} {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Toss order request failed: {exc.reason}") from exc

    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Toss order response does not contain result object.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest order detail.")
    parser.add_argument("order_id", help="Order ID from get_orders.py")
    parser.add_argument("--account-seq", type=int, help="Toss accountSeq from get_accounts.py")
    args = parser.parse_args()

    access_token = load_access_token()
    account_seq = args.account_seq or _get_default_account_seq(access_token)
    result = get_order(
        order_id=args.order_id,
        account_seq=account_seq,
        access_token=access_token,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
