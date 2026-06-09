# -*- coding: utf-8 -*-
"""Application-owned facade for market data lookups."""

from typing import Optional


def _wrapper_fetch_price(ticker: str, exchange: Optional[str] = None) -> float:
    from kis.wrapper import fetch_price as kis_fetch_price

    return kis_fetch_price(ticker, exchange)


def fetch_price(ticker: str, exchange: Optional[str] = None) -> float:
    """Fetch the latest REST price for a ticker through the KIS wrapper."""
    return _wrapper_fetch_price(ticker, exchange)
