"""Toss Invest stock ranking query helper."""

from __future__ import annotations

from typing import Callable, cast
from urllib import parse, request

from infrastructure.toss.auth import DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from infrastructure.toss.get_orderbook import _get_payload

_RANKING_TYPES = {
    "MARKET_TRADING_AMOUNT",
    "MARKET_TRADING_VOLUME",
    "TOP_GAINERS",
    "TOP_LOSERS",
    "TOSS_SECURITIES_TRADING_AMOUNT",
    "TOSS_SECURITIES_TRADING_VOLUME",
}
_DURATIONS = {"realtime", "1d", "1w", "1mo", "3mo", "6mo", "1y"}


def get_rankings(
    *,
    ranking_type: str,
    market_country: str,
    duration: str,
    access_token: str,
    exclude_investment_caution: bool | None = None,
    count: int | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> dict[str, object]:
    ranking_type = ranking_type.upper()
    market_country = market_country.upper()
    if ranking_type not in _RANKING_TYPES:
        raise ValueError("Unsupported ranking_type.")
    if market_country not in {"KR", "US"}:
        raise ValueError("market_country must be KR or US.")
    if duration not in _DURATIONS:
        raise ValueError("Unsupported ranking duration.")
    if duration == "realtime" and ranking_type in {"TOP_GAINERS", "TOP_LOSERS"}:
        raise ValueError("TOP_GAINERS and TOP_LOSERS do not support realtime.")
    if count is not None and not 1 <= count <= 100:
        raise ValueError("count must be between 1 and 100.")

    params: dict[str, object] = {
        "type": ranking_type,
        "marketCountry": market_country,
        "duration": duration,
    }
    if exclude_investment_caution is not None:
        params["excludeInvestmentCaution"] = str(exclude_investment_caution).lower()
    if count is not None:
        params["count"] = count
    url = f"{base_url.rstrip('/')}/api/v1/rankings?{parse.urlencode(params)}"
    return cast(
        dict[str, object],
        _get_payload(
            url=url,
            access_token=access_token,
            timeout=timeout,
            urlopen=urlopen,
            result_type=dict,
            name="rankings",
            group="RANKING",
        ),
    )
