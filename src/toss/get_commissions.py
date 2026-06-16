"""토스증권 매매 수수료 조회 API 래퍼.

GET /api/v1/commissions로 현재 계좌의 시장별 매매 수수료율을 조회한다.
계좌 헤더 X-Tossinvest-Account가 필요하며 Rate Limits Group은 ORDER_INFO다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable
from urllib import error, request

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from toss.auth import DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from toss.account_cache import get_default_account_seq
from toss.auth import load_access_token


def get_commissions(
    *,
    account_seq: int,
    access_token: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> list[dict[str, object]]:
    url = f"{base_url.rstrip('/')}/api/v1/commissions"
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
        raise RuntimeError(f"Toss commissions request failed: HTTP {exc.code} {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Toss commissions request failed: {exc.reason}") from exc

    result = payload.get("result")
    if not isinstance(result, list):
        raise RuntimeError("Toss commissions response does not contain result list.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest commissions.")
    parser.add_argument("--account-seq", type=int, help="Toss accountSeq from get_accounts.py")
    args = parser.parse_args()

    access_token = load_access_token()
    account_seq = args.account_seq or get_default_account_seq(access_token)
    result = get_commissions(account_seq=account_seq, access_token=access_token)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
