from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable
from urllib import request

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from toss.auth import DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from toss.client import request_json
from toss.auth import load_access_token


def get_accounts(
    *,
    access_token: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> list[dict[str, object]]:
    accounts_url = f"{base_url.rstrip('/')}/api/v1/accounts"
    accounts_request = request.Request(
        accounts_url,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )

    payload = request_json(
        accounts_request,
        group="ACCOUNT",
        action_name="accounts",
        timeout=timeout,
        urlopen=urlopen,
    )

    result = payload.get("result")
    if not isinstance(result, list):
        raise RuntimeError("Toss accounts response does not contain result list.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Toss Invest accounts.")
    parser.parse_args()

    accounts = get_accounts(access_token=load_access_token())
    print(json.dumps(accounts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
