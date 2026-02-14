# -*- coding: utf-8 -*-
"""
Data Service Module (Refactored)

This module provides centralized data access for the application.
It separates data fetching, caching, and transformation logic.
"""
import logging
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
from dataclasses import dataclass

from thread_comm import ThreadRequest, RequestType
from kis.kis_thread import request_portfolio, wait_for_response
from state.system_state import is_kis_ready
from display import add_alert
from data.config_manager import ConfigFile, load_json, save_json
from utils.market_utils import get_fear_and_greed
from trading_config import get_stock_info
from constants import PORTFOLIO_CACHE_EXPIRE

# =============================================================================
# Cache Management
# =============================================================================

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

# =============================================================================
# Portfolio Transformation Logic
# =============================================================================

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

        # 1. Stock Values
        us_stock_usd = 0.0
        kr_stock_krw = 0.0
        for h in holdings:
            ticker = h.get("ticker", "")
            val = h.get("qty", 0) * h.get("cur_price", h.get("avg_price", 0))
            if asset_info.get(ticker, {}).get("currency") == "KRW":
                kr_stock_krw += val
            else:
                us_stock_usd += val

        # 2. Cash Values
        us_cash_usd = sum(c.get("amount", 0) for c in cash_holdings if c.get("currency") == "USD")
        kr_cash_krw = sum(c.get("amount", 0) for c in cash_holdings if c.get("currency") == "KRW")

        # 3. Conversions
        us_stock_krw = us_stock_usd * ex_rate
        us_cash_krw = us_cash_usd * ex_rate
        kr_stock_usd = kr_stock_krw / ex_rate if ex_rate > 0 else 0
        kr_cash_usd = kr_cash_krw / ex_rate if ex_rate > 0 else 0

        # 4. Totals
        total_stock_usd = us_stock_usd + kr_stock_usd
        total_cash_usd = us_cash_usd + kr_cash_usd
        total_stock_krw = us_stock_krw + kr_stock_krw
        total_cash_krw = us_cash_krw + kr_cash_krw
        
        total_usd = total_stock_usd + total_cash_usd
        total_krw = total_stock_krw + total_cash_krw

        # 5. Ratios
        us_pct = ((us_stock_usd + us_cash_usd) / total_usd * 100) if total_usd > 0 else 0
        kr_pct = ((kr_stock_usd + kr_cash_usd) / total_usd * 100) if total_usd > 0 else 0
        
        us_cash_ratio = (us_cash_usd / (us_stock_usd + us_cash_usd) * 100) if (us_stock_usd + us_cash_usd) > 0 else 0
        kr_cash_ratio = (kr_cash_krw / (kr_stock_krw + kr_cash_krw) * 100) if (kr_stock_krw + kr_cash_krw) > 0 else 0

        return {
            "us_stock_usd": us_stock_usd, "us_cash_usd": us_cash_usd,
            "us_stock_krw": us_stock_krw, "us_cash_krw": us_cash_krw,
            "kr_stock_krw": kr_stock_krw, "kr_cash_krw": kr_cash_krw,
            "kr_stock_usd": kr_stock_usd, "kr_cash_usd": kr_cash_usd,
            "total_stock_usd": total_stock_usd, "total_cash_usd": total_cash_usd,
            "total_stock_krw": total_stock_krw, "total_cash_krw": total_cash_krw,
            "total_usd": total_usd, "total_krw": total_krw,
            "us_pct": us_pct, "kr_pct": kr_pct,
            "us_cash_ratio": us_cash_ratio, "kr_cash_ratio": kr_cash_ratio
        }

    @staticmethod
    def merge_holdings(raw_data: Dict) -> Tuple[Dict, float]:
        """Merge holdings by ticker and include cash as pseudo-tickers."""
        metadata = raw_data.get("metadata", {})
        ex_rate = metadata.get("exchange_rate", 1.0)
        asset_info = raw_data.get("asset_info", {})
        
        merged = {}
        total_usd = 0.0

        # Process Stocks
        for h in raw_data.get("holdings", []):
            ticker = h.get("ticker", "")
            info = asset_info.get(ticker, {})
            currency = info.get("currency", "USD")
            
            if ticker not in merged:
                merged[ticker] = {
                    "qty": 0.0, "total_investment": 0.0, "name": h.get("name", ticker),
                    "currency": currency, "type": "STOCK", "cur_price": h.get("cur_price", 0)
                }
            
            merged[ticker]["qty"] += h.get("qty", 0)
            merged[ticker]["total_investment"] += h.get("qty", 0) * h.get("avg_price", 0)

        # Process Cash
        for c in raw_data.get("cash_holdings", []):
            curr = c.get("currency", "USD")
            key = f"{curr} cash"
            if key not in merged:
                merged[key] = {"qty": 0, "cur_price": 1.0, "name": key, "currency": curr, "type": "CASH"}
            merged[key]["qty"] += c.get("amount", 0)

        # Calculate Values
        for t, data in merged.items():
            val_native = data["qty"] * data["cur_price"]
            if data["currency"] == "USD":
                data["current_value_usd"] = val_native
                data["current_value_krw"] = val_native * ex_rate
            else:
                data["current_value_krw"] = val_native
                data["current_value_usd"] = val_native / ex_rate
            total_usd += data["current_value_usd"]

        return merged, total_usd

# =============================================================================
# Main Service Functions
# =============================================================================

def get_portfolio_data(force_refresh: bool = False, scope: str = "all") -> Dict:
    """
    Orchestrates portfolio data fetching and processing.
    """
    # 1. Try Cache
    cached = PortfolioCacheManager.get(force_refresh)
    if cached:
        logging.info("[DataService] Using cached portfolio data")
        add_alert("[Data] Using cached portfolio", "DEBUG")
        return _apply_scope_filter(cached, scope)

    logging.info("[DataService] Fetching fresh portfolio data (cache missed/force)")

    # 2. Fetch from KIS
    if not is_kis_ready():
        return {"error": "KIS Thread not ready"}

    add_alert("[Data] Fetching portfolio...", "INFO")
    request_id = request_portfolio(force_refresh=force_refresh)
    response = wait_for_response(request_id, timeout=60.0)

    if not response or not response.success:
        return {"error": response.error if response else "Timeout"}

    raw_portfolio = response.result
    save_json(ConfigFile.PORTFOLIO, raw_portfolio)

    # 3. Process Data
    processor = PortfolioProcessor()
    merged_data, total_usd = processor.merge_holdings(raw_portfolio)
    stats = processor.calculate_stats(raw_portfolio)

    result = {
        "raw": raw_portfolio,
        "merged_data": merged_data,
        "total_value_usd": total_usd,
        "stats": stats,
        "exchange_rate": raw_portfolio.get("metadata", {}).get("exchange_rate"),
        "price_map": {t: d["cur_price"] for t, d in merged_data.items() if d["type"] == "STOCK"},
        "accounts": raw_portfolio.get("accounts", []),
        "holdings": raw_portfolio.get("holdings", []),
        "metadata": raw_portfolio.get("metadata", {})
    }

    # 4. Calculate Weights
    try:
        from data.calculate_weights import calculate_target_weights
        weights_cfg = load_json(ConfigFile.PORTFOLIO_WEIGHTS)
        cur_weights = {t: d["current_value_usd"] / total_usd for t, d in merged_data.items() if total_usd > 0}
        result["current_weights"] = cur_weights
        result["targets"], _, _ = calculate_target_weights(cur_weights, weights_cfg, get_fear_and_greed())
    except Exception as e:
        logging.error(f"Weight calc error: {e}")
        result["targets"] = {}

    # 5. Cache if no critical errors
    if not (result["metadata"].get("gsheet_error") or result["metadata"].get("kis_error")):
        PortfolioCacheManager.set(result)
        add_alert("[Data] Portfolio loaded", "SUCCESS")
    else:
        add_alert("[Data] Portfolio loaded (partial)", "WARN")

    return _apply_scope_filter(result, scope)

def _apply_scope_filter(data: Dict, scope: str) -> Dict:
    """Filters processed data by account scope (all/kis/passive)."""
    if scope == "all": return data

    raw = data["raw"]
    accounts = raw.get("accounts", [])
    kis_ids = {a["id"] for a in accounts if a.get("name") == "한국투자증권"}
    
    target_ids = kis_ids if scope == "kis" else ({a["id"] for a in accounts} - kis_ids)
    
    # DEBUG LOG
    logging.info(f"[Filter] Scope: {scope}, TargetIDs: {target_ids}")
    all_cash = raw.get("cash_holdings", [])
    logging.info(f"[Filter] Raw Cash Count: {len(all_cash)}")
    for c in all_cash:
        logging.info(f"  - Cash: {c.get('account_name')} | ID: {c.get('account_id')} | Amt: {c.get('amount')}")

    # Re-run processing on filtered raw data
    target_names = {a["name"] for a in accounts if a["id"] in target_ids}
    filtered_cash = [c for c in all_cash if (c.get("account_id") in target_ids or c.get("account_name") in target_names)]
    
    logging.info(f"[Filter] Filtered Cash Count: {len(filtered_cash)}")

    filtered_raw = {
        "metadata": raw.get("metadata", {}),
        "asset_info": raw.get("asset_info", {}),
        "holdings": [h for h in raw.get("holdings", []) if h.get("account_id") in target_ids],
        "cash_holdings": filtered_cash
    }

    processor = PortfolioProcessor()
    merged, total = processor.merge_holdings(filtered_raw)
    stats = processor.calculate_stats(filtered_raw)
    
    scoped_result = dict(data)
    scoped_result.update({
        "merged_data": merged, "total_value_usd": total, "stats": stats,
        "holdings": filtered_raw["holdings"],
        "current_weights": {t: d["current_value_usd"] / total for t, d in merged.items() if total > 0}
    })
    return scoped_result

def get_weight_diffs(scope: str = "all") -> Tuple[List[Dict], float, Dict]:
    """Calculates rebalancing differences."""
    portfolio = get_portfolio_data(scope=scope)
    merged = portfolio.get("merged_data", {})
    total_usd = portfolio.get("total_value_usd", 0.0)
    targets = portfolio.get("targets", {})
    ex_rate = portfolio.get("exchange_rate", 1.0)

    # 1. Aggregate Groups
    try:
        cfg = load_json(ConfigFile.PORTFOLIO_WEIGHTS)
        group_map = {g['main_ticker']: g.get('constituents', []) for g in cfg.get('groups', [])}
        constituents = {c for sublist in group_map.values() for c in sublist}
    except:
        group_map, constituents = {}, set()

    cur_weights = dict(portfolio.get("current_weights", {}))
    for main, subs in group_map.items():
        for s in subs:
            if s in cur_weights:
                cur_weights[main] = cur_weights.get(main, 0.0) + cur_weights.pop(s, 0.0)

    # 2. Calculate Diffs
    diffs = []
    all_tickers = (set(cur_weights.keys()) | set(targets.keys())) - constituents
    
    for t in all_tickers:
        if "cash" in t.lower(): continue
        
        cur_w, tgt_w = cur_weights.get(t, 0.0), targets.get(t, 0.0)
        diff = tgt_w - cur_w
        data = merged.get(t, {})
        
        # Quantity calculation
        price = data.get("cur_price", 0.0)
        if price <= 0:
            from kis.wrapper import fetch_price
            price = fetch_price(t)

        qty_diff = 0
        if price > 0:
            val_diff_native = (diff * total_usd) * (ex_rate if data.get("currency") == "KRW" else 1.0)
            qty_diff = int(val_diff_native / price)

        diffs.append({
            "ticker": t, "name": data.get("name", t), "cur_w": cur_w, "tgt_w": tgt_w,
            "diff": diff, "abs_diff": abs(diff), "qty_diff": qty_diff
        })

    diffs.sort(key=lambda x: x["abs_diff"], reverse=True)

    # 3. Cash Info
    current_cash = sum(d["current_value_usd"] for d in merged.values() if d["type"] == "CASH")
    target_cash = 0.1
    try:
        from data.calculate_weights import get_cash_weight
        target_cash = get_cash_weight(get_fear_and_greed(), cfg.get('cash_strategy', {}))
    except: pass

    return diffs, total_usd, {"current": current_cash/total_usd if total_usd > 0 else 0, "target": target_cash}

def invalidate_cache():
    PortfolioCacheManager.invalidate()
