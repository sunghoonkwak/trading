"""Toss Invest market-indicator query helpers."""

from __future__ import annotations

from typing import Callable, Sequence, cast
from urllib import parse, request

from infrastructure.toss.auth import DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from infrastructure.toss.get_orderbook import _get_payload

_INDICATORS = {
    "KOSPI",
    "KOSDAQ",
    "KR_BOND_2Y",
    "KR_BOND_3Y",
    "KR_BOND_5Y",
    "KR_BOND_10Y",
    "KR_BOND_20Y",
    "KR_BOND_30Y",
}


def get_market_indicator_prices(
    symbols: Sequence[str],
    *,
    access_token: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> list[dict[str, object]]:
    cleaned = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
    if not cleaned or any(symbol not in _INDICATORS for symbol in cleaned):
        raise ValueError("At least one supported market indicator symbol is required.")
    if len(cleaned) > 200:
        raise ValueError("Toss market indicators API supports up to 200 symbols.")
    url = f"{base_url.rstrip('/')}/api/v1/market-indicators/prices?{parse.urlencode({'symbols': ','.join(cleaned)})}"
    return cast(
        list[dict[str, object]],
        _get_payload(
            url=url,
            access_token=access_token,
            timeout=timeout,
            urlopen=urlopen,
            result_type=list,
            name="market indicator prices",
            group="MARKET_INDICATOR",
        ),
    )


def get_market_indicator_candles(
    *,
    symbol: str,
    interval: str,
    access_token: str,
    count: int | None = None,
    before: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    symbol = symbol.strip().upper()
    if symbol not in _INDICATORS:
        raise ValueError("Unsupported market indicator symbol.")
    if interval not in {"1m", "1d"}:
        raise ValueError("interval must be 1m or 1d.")
    if symbol.startswith("KR_BOND_") and interval != "1d":
        raise ValueError("Korean bond indicators support only 1d candles.")
    if count is not None and not 1 <= count <= 200:
        raise ValueError("count must be between 1 and 200.")
    params: dict[str, object] = {"interval": interval}
    if count is not None:
        params["count"] = count
    if before:
        params["before"] = before
    encoded_symbol = parse.quote(symbol, safe="")
    url = f"{base_url.rstrip('/')}/api/v1/market-indicators/{encoded_symbol}/candles?{parse.urlencode(params)}"
    return cast(
        dict[str, object],
        _get_payload(
            url=url,
            access_token=access_token,
            timeout=timeout,
            urlopen=urlopen,
            result_type=dict,
            name="market indicator candles",
            group="MARKET_INDICATOR_CHART",
        ),
    )


def get_market_indicator_investor_trading(
    *,
    symbol: str,
    interval: str,
    access_token: str,
    count: int | None = None,
    until: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    symbol = symbol.strip().upper()
    if symbol not in {"KOSPI", "KOSDAQ"}:
        raise ValueError("Investor trading supports KOSPI or KOSDAQ.")
    if interval not in {"1d", "1w", "1mo", "1y"}:
        raise ValueError("Unsupported investor trading interval.")
    if count is not None and not 1 <= count <= 100:
        raise ValueError("count must be between 1 and 100.")
    params: dict[str, object] = {"interval": interval}
    if count is not None:
        params["count"] = count
    if until:
        params["until"] = until
    encoded_symbol = parse.quote(symbol, safe="")
    url = f"{base_url.rstrip('/')}/api/v1/market-indicators/{encoded_symbol}/investor-trading?{parse.urlencode(params)}"
    return cast(
        dict[str, object],
        _get_payload(
            url=url,
            access_token=access_token,
            timeout=timeout,
            urlopen=urlopen,
            result_type=dict,
            name="market indicator investor trading",
            group="MARKET_INDICATOR",
        ),
    )
