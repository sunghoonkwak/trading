# -*- coding: utf-8 -*-
"""Application-owned facade for market data lookups."""

from typing import Optional


def _wrapper_fetch_price(ticker: str, exchange: Optional[str] = None) -> float:
    from kis.wrapper import fetch_price as kis_fetch_price

    return kis_fetch_price(ticker, exchange)


def fetch_price(ticker: str, exchange: Optional[str] = None) -> float:
    """Fetch the latest REST price for a ticker through the KIS wrapper."""
    return _wrapper_fetch_price(ticker, exchange)


def _wrapper_get_current_price(ticker: str) -> float:
    from kis.wrapper import get_current_price as kis_get_current_price

    return kis_get_current_price(ticker)


def get_current_price(ticker: str) -> float:
    """Return the current cached WebSocket price for a ticker."""
    return _wrapper_get_current_price(ticker)
