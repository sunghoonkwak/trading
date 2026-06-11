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


def get_exchange_rate(
    *,
    base_currency: str,
    quote_currency: str,
    access_token: str,
    date_time: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    params = {
        "baseCurrency": base_currency.upper(),
        "quoteCurrency": quote_currency.upper(),
    }
    if date_time:
        params["dateTime"] = date_time

    url = f"{base_url.rstrip('/')}/api/v1/exchange-rate?{parse.urlencode(params)}"
    return _get_result_object(url=url, access_token=access_token, timeout=timeout, urlopen=urlopen, name="exchange-rate")


def _get_result_object(
    *,
    url: str,
    access_token: str,
    timeout: float,
    urlopen: Callable[..., object],
    name: str,
) -> dict[str, object]:
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
    if not isinstance(result, dict):
        raise RuntimeError(f"Toss {name} response does not contain result object.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest exchange rate.")
    parser.add_argument("--base-currency", default="USD")
    parser.add_argument("--quote-currency", default="KRW")
    parser.add_argument("--date-time", help="Optional ISO date-time, e.g. 2026-03-25T09:30:00+09:00")
    args = parser.parse_args()

    result = get_exchange_rate(
        base_currency=args.base_currency,
        quote_currency=args.quote_currency,
        date_time=args.date_time,
        access_token=load_access_token(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
