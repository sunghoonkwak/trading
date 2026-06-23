# -*- coding: utf-8 -*-
"""Application-owned facade for market data lookups."""

import logging
from typing import Dict, Iterable, Optional

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


def fetch_prices(tickers: Iterable[str]) -> Dict[str, float]:
    """Fetch current prices through Toss first, then fill gaps with KIS."""
    symbols = sorted(
        {
            str(ticker).strip().upper()
            for ticker in tickers
            if str(ticker).strip()
        }
    )
    if not symbols:
        return {}

    prices: Dict[str, float] = {}
    try:
        from toss.auth import load_access_token
        from toss.get_prices import get_prices

        for start in range(0, len(symbols), 200):
            batch = symbols[start:start + 200]
            for item in get_prices(batch, access_token=load_access_token()):
                symbol = str(item.get("symbol", "")).strip().upper()
                price = _to_positive_float(item.get("lastPrice"))
                if symbol and price > 0:
                    prices[symbol] = price
    except Exception as e:
        logging.warning(f"[MarketData] Toss batch price fetch failed: {e}")

    for symbol in symbols:
        if prices.get(symbol, 0.0) <= 0:
            price = fetch_price(symbol)
            if price > 0:
                prices[symbol] = price

    return prices


def _to_positive_float(value) -> float:
    try:
        price = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0
    return price if price > 0 else 0.0


def get_current_price(ticker: str) -> float:
    """Return the current Toss-first price for a ticker."""
    symbol = str(ticker).strip().upper()
    if not symbol:
        return 0.0
    return fetch_prices([symbol]).get(symbol, 0.0)
