"""Process-local Toss account lookup cache."""

from __future__ import annotations

from threading import Lock
from typing import Callable
from urllib import request

from toss.auth import DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from toss.get_accounts import get_accounts


_DEFAULT_ACCOUNT_CACHE: dict[tuple[str, str], int] = {}
_CACHE_LOCK = Lock()


def get_default_account_seq(
    access_token: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> int:
    """Return the first Toss accountSeq, caching it for the token lifetime."""
    cache_key = (access_token, base_url.rstrip("/"))
    with _CACHE_LOCK:
        account_seq = _DEFAULT_ACCOUNT_CACHE.get(cache_key)
    if account_seq is not None:
        return account_seq

    accounts = get_accounts(
        access_token=access_token,
        base_url=base_url,
        timeout=timeout,
        urlopen=urlopen,
    )
    if not accounts:
        raise RuntimeError("No Toss account found. Cannot query account API.")

    account_seq = accounts[0].get("accountSeq")
    if not isinstance(account_seq, int):
        raise RuntimeError("First Toss account does not contain integer accountSeq.")

    with _CACHE_LOCK:
        _DEFAULT_ACCOUNT_CACHE[cache_key] = account_seq
    return account_seq


def clear_default_account_cache() -> None:
    """Clear cached Toss accountSeq values for tests and diagnostics."""
    with _CACHE_LOCK:
        _DEFAULT_ACCOUNT_CACHE.clear()
