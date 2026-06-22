# -*- coding: utf-8 -*-
"""Application-owned facade for market data lookups."""

import logging
from typing import Optional

from core import trading_config


def _get_price_module():
    from kis.kis_api.overseas_stock.price import price as price_module

    return price_module


def fetch_price(ticker: str, exchange: Optional[str] = None) -> float:
    """Fetch the latest REST price for a ticker through the KIS price API."""
    if not trading_config.is_kis_rest_api_enabled():
        return 0.0

    if not exchange:
        exchange = trading_config.get_kis_exchange_code(ticker)
    try:
        df = _get_price_module().price("", exchange, ticker.upper(), "real")
        if df is not None and not df.empty:
            row = df.iloc[0]
            for field in ['last', 'base', 'ovrs_stck_prpr', 'stck_prpr', 'prpr', 'clpr']:
                val = row.get(field)
                if val and float(val) > 0:
                    return float(val)
        return 0.0
    except Exception as e:
        logging.warning(f"[MarketData] {ticker} price fetch failed: {e}")
        return 0.0


def _get_market_manager():
    from state.market_state import get_market_manager

    return get_market_manager()


def get_current_price(ticker: str) -> float:
    """Return the current cached WebSocket price for a ticker."""
    return _get_market_manager().get_price(ticker)
