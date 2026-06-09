# -*- coding: utf-8 -*-
"""Portfolio cache and transformation helpers."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple

from core.constants import PORTFOLIO_CACHE_EXPIRE


@dataclass
class PortfolioCache:
    data: Dict
    timestamp: datetime
    expire_seconds: int = PORTFOLIO_CACHE_EXPIRE

    def is_expired(self) -> bool:
        return (datetime.now() - self.timestamp).total_seconds() > self.expire_seconds


class PortfolioCacheManager:
    _cache: Optional[PortfolioCache] = None

    @classmethod
    def get(cls, force_refresh: bool = False) -> Optional[Dict]:
        if force_refresh or cls._cache is None or cls._cache.is_expired():
            return None
        return cls._cache.data

    @classmethod
    def set(cls, data: Dict):
        cls._cache = PortfolioCache(data=data, timestamp=datetime.now())

    @classmethod
    def invalidate(cls):
        cls._cache = None


class PortfolioProcessor:
    """Handles merging, statistics, and weight calculations for portfolio data."""

    @staticmethod
    def calculate_stats(raw_data: Dict) -> Dict:
        """Calculate USD/KRW totals and percentages with full breakdown."""
        metadata = raw_data.get("metadata", {})
        ex_rate = metadata.get("exchange_rate", 1.0)

        asset_info = raw_data.get("asset_info", {})
        holdings = raw_data.get("holdings", [])
        cash_holdings = raw_data.get("cash_holdings", [])

        us_stock_usd = 0.0
        kr_stock_krw = 0.0
        for h in holdings:
            ticker = h.get("ticker", "")
            val = h.get("qty", 0) * h.get("cur_price", h.get("avg_price", 0))
            if asset_info.get(ticker, {}).get("currency") == "KRW":
                kr_stock_krw += val
            else:
                us_stock_usd += val

        us_cash_usd = sum(
            c.get("amount", 0)
            for c in cash_holdings
            if c.get("currency") == "USD"
        )
        kr_cash_krw = sum(
            c.get("amount", 0)
            for c in cash_holdings
            if c.get("currency") == "KRW"
        )

        us_stock_krw = us_stock_usd * ex_rate
        us_cash_krw = us_cash_usd * ex_rate
        kr_stock_usd = kr_stock_krw / ex_rate if ex_rate > 0 else 0
        kr_cash_usd = kr_cash_krw / ex_rate if ex_rate > 0 else 0

        total_stock_usd = us_stock_usd + kr_stock_usd
        total_cash_usd = us_cash_usd + kr_cash_usd
        total_stock_krw = us_stock_krw + kr_stock_krw
        total_cash_krw = us_cash_krw + kr_cash_krw

        total_usd = total_stock_usd + total_cash_usd
        total_krw = total_stock_krw + total_cash_krw

        us_pct = (
            (us_stock_usd + us_cash_usd) / total_usd * 100
            if total_usd > 0
            else 0
        )
        kr_pct = (
            (kr_stock_usd + kr_cash_usd) / total_usd * 100
            if total_usd > 0
            else 0
        )

        us_cash_ratio = (
            us_cash_usd / (us_stock_usd + us_cash_usd) * 100
            if (us_stock_usd + us_cash_usd) > 0
            else 0
        )
        kr_cash_ratio = (
            kr_cash_krw / (kr_stock_krw + kr_cash_krw) * 100
            if (kr_stock_krw + kr_cash_krw) > 0
            else 0
        )

        return {
            "us_stock_usd": us_stock_usd,
            "us_cash_usd": us_cash_usd,
            "us_stock_krw": us_stock_krw,
            "us_cash_krw": us_cash_krw,
            "kr_stock_krw": kr_stock_krw,
            "kr_cash_krw": kr_cash_krw,
            "kr_stock_usd": kr_stock_usd,
            "kr_cash_usd": kr_cash_usd,
            "total_stock_usd": total_stock_usd,
            "total_cash_usd": total_cash_usd,
            "total_stock_krw": total_stock_krw,
            "total_cash_krw": total_cash_krw,
            "total_usd": total_usd,
            "total_krw": total_krw,
            "us_pct": us_pct,
            "kr_pct": kr_pct,
            "us_cash_ratio": us_cash_ratio,
            "kr_cash_ratio": kr_cash_ratio,
        }

    @staticmethod
    def merge_holdings(raw_data: Dict) -> Tuple[Dict, float]:
        """Merge holdings by ticker and include cash as pseudo-tickers."""
        metadata = raw_data.get("metadata", {})
        ex_rate = metadata.get("exchange_rate", 1.0)
        asset_info = raw_data.get("asset_info", {})

        merged = {}
        total_usd = 0.0

        for h in raw_data.get("holdings", []):
            ticker = h.get("ticker", "")
            info = asset_info.get(ticker, {})
            currency = info.get("currency", "USD")

            if ticker not in merged:
                merged[ticker] = {
                    "qty": 0.0,
                    "total_investment": 0.0,
                    "name": h.get("name", ticker),
                    "currency": currency,
                    "type": "STOCK",
                    "cur_price": h.get("cur_price", 0),
                }

            merged[ticker]["qty"] += h.get("qty", 0)
            merged[ticker]["total_investment"] += (
                h.get("qty", 0) * h.get("avg_price", 0)
            )

        for c in raw_data.get("cash_holdings", []):
            curr = c.get("currency", "USD")
            key = f"{curr} cash"
            if key not in merged:
                merged[key] = {
                    "qty": 0,
                    "cur_price": 1.0,
                    "name": key,
                    "currency": curr,
                    "type": "CASH",
                }
            merged[key]["qty"] += c.get("amount", 0)

        for data in merged.values():
            val_native = data["qty"] * data["cur_price"]
            if data["currency"] == "USD":
                data["current_value_usd"] = val_native
                data["current_value_krw"] = val_native * ex_rate
            else:
                if ex_rate <= 0:
                    raise ValueError(
                        "Cannot convert KRW portfolio values without a positive exchange rate"
                    )
                data["current_value_krw"] = val_native
                data["current_value_usd"] = val_native / ex_rate

            if data.get("type") == "CASH":
                data["avg_price"] = 1.0
                data["total_investment"] = data["qty"]
            elif data.get("qty", 0) > 0:
                data["avg_price"] = data.get("total_investment", 0.0) / data["qty"]
            else:
                data["avg_price"] = 0.0

            total_usd += data["current_value_usd"]

        return merged, total_usd
