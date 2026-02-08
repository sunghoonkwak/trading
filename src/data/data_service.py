# -*- coding: utf-8 -*-
"""
Data Service Module

This module provides centralized data access for the Main Thread.
It handles caching, KIS Thread requests, and data transformation.

All data requests from menu handlers (handle_account_info, handle_place_order, etc.)
should go through this module.
"""
import logging
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from thread_comm import ThreadRequest, RequestType
from kis.kis_thread import request_portfolio, wait_for_response
from thread_state import is_kis_ready
from display import add_alert
import json
import os

# Path to portfolio.json - in KIS_config directory
CONFIG_ROOT = os.path.join(os.path.expanduser("~"), "KIS_config")
PORTFOLIO_FILE = os.path.join(CONFIG_ROOT, 'portfolio.json')

# =============================================================================
# Portfolio Cache
# =============================================================================

@dataclass
class PortfolioCache:
    """
    Cache container for portfolio data.

    Attributes:
        data: The cached get_portfolio() result
        timestamp: When the data was fetched
        expire_seconds: Cache expiration time (default: 5 minutes)
    """
    data: dict
    timestamp: datetime
    expire_seconds: int = 300  # 5 minutes

    def is_expired(self) -> bool:
        """Check if the cache has expired."""
        elapsed = (datetime.now() - self.timestamp).total_seconds()
        return elapsed > self.expire_seconds


_portfolio_cache: Optional[PortfolioCache] = None


def get_cached_portfolio(force_refresh: bool = False) -> Optional[dict]:
    """Get cached portfolio data, or None if expired/missing."""
    global _portfolio_cache

    if force_refresh:
        return None

    if _portfolio_cache is None or _portfolio_cache.is_expired():
        return None

    return _portfolio_cache.data


def set_portfolio_cache(data: dict) -> None:
    """Update the portfolio cache with new data."""
    global _portfolio_cache
    _portfolio_cache = PortfolioCache(
        data=data,
        timestamp=datetime.now()
    )


def clear_portfolio_cache() -> None:
    """Clear the portfolio cache."""
    global _portfolio_cache
    _portfolio_cache = None


# =============================================================================
# Data Access Functions
# =============================================================================

def _load_portfolio() -> dict:
    """Load portfolio data from portfolio.json."""
    try:
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}


def _calculate_portfolio_stats(portfolio_data: dict) -> dict:
    """
    Calculate portfolio statistics with USD/KRW breakdown.

    Args:
        portfolio_data: Full portfolio data from get_portfolio()

    Returns:
        dict with us_stock_usd, us_cash_usd, kr_stock_krw, kr_cash_krw, etc.
    """
    if portfolio_data is None:
        portfolio_data = _load_portfolio()

    if "error" in portfolio_data:
        return {"error": portfolio_data["error"]}

    # Extract exchange_rate from metadata
    exchange_rate = portfolio_data.get("metadata", {}).get("exchange_rate")
    if exchange_rate is None:
        return {"error": "exchange_rate not found in portfolio metadata"}

    # Initialize totals
    us_stock_usd = 0.0
    us_cash_usd = 0.0
    kr_stock_krw = 0.0
    kr_cash_krw = 0.0

    # Calculate stock values using holdings cur_price
    asset_info = portfolio_data.get("asset_info", {})
    holdings = portfolio_data.get("holdings", [])

    for h in holdings:
        ticker = h.get("ticker", "")
        qty = h.get("qty", 0)
        avg_price = h.get("avg_price", 0)
        cur_price = h.get("cur_price", avg_price)  # Fallback to avg_price
        value = qty * cur_price

        # Determine currency from asset_info
        info = asset_info.get(ticker, {})
        currency = info.get("currency", "USD")

        if currency == "USD":
            us_stock_usd += value
        else:
            kr_stock_krw += value

    # Calculate cash holdings
    cash_holdings = portfolio_data.get("cash_holdings", [])
    for c in cash_holdings:
        amount = c.get("amount", 0)
        currency = c.get("currency", "USD")
        if currency == "USD":
            us_cash_usd += amount
        else:
            kr_cash_krw += amount

    # Convert with exchange rate
    us_stock_krw = us_stock_usd * exchange_rate
    us_cash_krw = us_cash_usd * exchange_rate
    kr_stock_usd = kr_stock_krw / exchange_rate if exchange_rate > 0 else 0
    kr_cash_usd = kr_cash_krw / exchange_rate if exchange_rate > 0 else 0

    # Calculate totals
    total_usd = us_stock_usd + us_cash_usd + kr_stock_usd + kr_cash_usd
    total_krw = us_stock_krw + us_cash_krw + kr_stock_krw + kr_cash_krw

    # Percentages - based on USD total
    us_pct = ((us_stock_usd + us_cash_usd) / total_usd * 100) if total_usd > 0 else 0
    kr_pct = ((kr_stock_usd + kr_cash_usd) / total_usd * 100) if total_usd > 0 else 0

    # Cash ratios within each currency's total assets
    us_total_assets = us_stock_usd + us_cash_usd
    kr_total_assets = kr_stock_krw + kr_cash_krw
    us_cash_ratio = (us_cash_usd / us_total_assets * 100) if us_total_assets > 0 else 0
    kr_cash_ratio = (kr_cash_krw / kr_total_assets * 100) if kr_total_assets > 0 else 0

    return {
        "us_stock_usd": us_stock_usd,
        "us_cash_usd": us_cash_usd,
        "us_stock_krw": us_stock_krw,
        "us_cash_krw": us_cash_krw,
        "kr_stock_usd": kr_stock_usd,
        "kr_cash_usd": kr_cash_usd,
        "kr_stock_krw": kr_stock_krw,
        "kr_cash_krw": kr_cash_krw,
        "total_stock_usd": us_stock_usd + kr_stock_usd,
        "total_cash_usd": us_cash_usd + kr_cash_usd,
        "total_stock_krw": us_stock_krw + kr_stock_krw,
        "total_cash_krw": us_cash_krw + kr_cash_krw,
        "us_pct": us_pct,
        "kr_pct": kr_pct,
        "us_cash_ratio": us_cash_ratio,
        "kr_cash_ratio": kr_cash_ratio
    }

def _get_merged_portfolio_stat(portfolio_data: dict):
    """
    Load portfolio, merge holdings by ticker, and calculate total value.
    Returns:
        (merged_dict, total_value_usd)

    merged_dict format:
    {
        ticker: {
            "qty", "total_investment_krw", "cur_price", "name", "currency",
            "current_value_usd", "current_value_krw", ...
        }
    }
    """
    if portfolio_data is None:
        portfolio_data = _load_portfolio()

    if "error" in portfolio_data:
        return {}, 0.0

    # Extract exchange_rate from metadata
    exchange_rate = portfolio_data.get("metadata", {}).get("exchange_rate")
    if exchange_rate is None:
        logging.error("exchange_rate not found in portfolio metadata")
        return {}, 0.0

    asset_info = portfolio_data.get("asset_info", {})
    holdings = portfolio_data.get("holdings", [])
    cash_holdings = portfolio_data.get("cash_holdings", [])

    merged = {}
    total_val_usd = 0.0

    # 1. Process Stocks
    for h in holdings:
        ticker = h.get("ticker", "")
        qty = h.get("qty", 0)
        avg_price = h.get("avg_price", 0)
        cur_price = h.get("cur_price", avg_price)  # Fallback to avg_price
        info = asset_info.get(ticker, {})
        name = h.get("name", info.get("name", ticker))
        currency = info.get("currency", "USD")

        if ticker not in merged:
            merged[ticker] = {
                "qty": 0.0,
                "total_investment": 0.0,
                "cur_price": cur_price,
                "name": name,
                "currency": currency,
                "type": "STOCK"
            }

        # Aggregate
        merged[ticker]["qty"] += qty
        merged[ticker]["total_investment"] += qty * avg_price
        if cur_price > 0:
            merged[ticker]["cur_price"] = cur_price

    # 2. Process Cash (USD/KRW) - Create as pseudo-tickers for weight calc
    usd_cash = sum(c["amount"] for c in cash_holdings if c.get("currency") == "USD")
    krw_cash = sum(c["amount"] for c in cash_holdings if c.get("currency") == "KRW")

    if usd_cash > 0:
        merged["USD cash"] = {
            "qty": usd_cash, "total_investment": usd_cash, "cur_price": 1.0,
            "name": "USD cash", "currency": "USD", "type": "CASH"
        }

    if krw_cash > 0:
        merged["KRW cash"] = {
            "qty": krw_cash, "total_investment": krw_cash, "cur_price": 1.0,
            "name": "KRW cash", "currency": "KRW", "type": "CASH"
        }

    # 3. Calculate Values & Total
    for ticker, data in merged.items():
        qty = data["qty"]
        cur_price = data["cur_price"]
        currency = data["currency"]

        # Value in native currency
        val_native = qty * cur_price
        data["current_value_native"] = val_native

        # Convert to USD for uniform weight calculation
        if currency == "USD":
            val_usd = val_native
            val_krw = val_native * exchange_rate
        else:
            val_krw = val_native
            val_usd = val_native / exchange_rate if exchange_rate > 0 else 0

        data["current_value_usd"] = val_usd
        data["current_value_krw"] = val_krw

        total_val_usd += val_usd

    return merged, total_val_usd

def get_portfolio_data(force_refresh: bool = False) -> dict:
    """
    Get portfolio data with caching support.

    This function:
    1. Checks cache for valid data
    2. If cache hit, returns cached data immediately
    3. If cache miss/expired, requests from KIS Thread
    4. Stores response in cache and returns

    Args:
        force_refresh: If True, bypass cache and force a new request

    Returns:
        dict: Portfolio data from get_portfolio() or error dict
    """
    # Check if KIS Thread is ready
    if not is_kis_ready():
        return {"error": "KIS Thread not authenticated"}

    # Check cache first (unless force_refresh)
    cached = get_cached_portfolio(force_refresh=force_refresh)
    if cached is not None:
        add_alert("[Data] Using cached portfolio", "DEBUG")
        logging.debug("[DataService] Returning cached portfolio data")
        return cached

    # Cache miss - request from KIS Thread
    add_alert("[Data] Fetching portfolio...", "INFO")
    logging.info("[DataService] Requesting portfolio from KIS Thread")

    request_id = request_portfolio(force_refresh=force_refresh)
    response = wait_for_response(request_id, timeout=60.0)

    if response is None:
        error_msg = "Portfolio request timed out"
        logging.error(f"[DataService] {error_msg}")
        return {"error": error_msg}

    if not response.success:
        error_msg = response.error or "Unknown error"
        logging.error(f"[DataService] Portfolio request failed: {error_msg}")
        return {"error": error_msg}

    # Process the successful response (raw portfolio dict)
    raw_portfolio = response.result

    try:
        with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
            json.dump(raw_portfolio, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"[Data] Failed to save portfolio: {e}")
        add_alert(f"Failed to save portfolio: {e}", "ERROR")

    # --- Processing Logic (formerly in get_portfolio) ---
    result = {
        "merged_data": {},
        "total_value_usd": 0.0,
        "current_weights": {},
        "targets": {},
        "stats": {},
        "exchange_rate": None,
        "error": None
    }

    # Extract metadata and prices
    metadata = raw_portfolio.get("metadata", {})
    exchange_rate = float(metadata.get("exchange_rate", None))
    result["exchange_rate"] = exchange_rate

    current_prices = {}
    holdings = raw_portfolio.get("holdings", [])
    for h in holdings:
        ticker = h.get("ticker", "")
        cur_price = h.get("cur_price", 0.0)
        if ticker and cur_price > 0:
            current_prices[ticker] = cur_price

    result["price_map"] = current_prices

    # Calculate stats using imported helper
    stats = _calculate_portfolio_stats(raw_portfolio)
    if "error" in stats:
        result["error"] = stats["error"]
        return result
    result["stats"] = stats

    # Get merged data using imported helper
    merged_data, total_value_usd = _get_merged_portfolio_stat(raw_portfolio)
    result["merged_data"] = merged_data
    result["total_value_usd"] = total_value_usd

    # Include raw lists for consumers (e.g. web_server)
    result["holdings"] = raw_portfolio.get("holdings", [])
    result["accounts"] = raw_portfolio.get("accounts", [])
    result["metadata"] = raw_portfolio.get("metadata", {})

    # Calculate current weights
    current_weights = {}
    if total_value_usd > 0:
        for ticker, data in merged_data.items():
            current_weights[ticker] = data["current_value_usd"] / total_value_usd
    result["current_weights"] = current_weights

    # Calculate target weights
    targets = {}
    try:
        try:
            from data.calculate_weights import calculate_target_weights, load_config
        except ImportError:
            def calculate_target_weights(c, cfg, fg=50.0): return {}, 0, 0.2
            def load_config(p): return {}

        # Path resolution for weights config (in KIS_config directory)
        import os
        config_path = os.path.join(os.path.expanduser("~"), "KIS_config", "portfolio_weights.json")

        if not os.path.exists(config_path):
            logging.warning(f"[Data] portfolio_weights.json not found at {config_path}")

        config = load_config(config_path)

        # Get F&G index from cached utility
        try:
            from utils import get_fear_and_greed
            fear_greed_index = get_fear_and_greed()
        except ImportError:
            fear_greed_index = 50.0

        targets, score, cash_weight = calculate_target_weights(current_weights, config, fear_greed_index)
    except Exception as e:
        logging.error(f"[DataService] Weight calc error: {e}")
        targets = {}

    result["targets"] = targets

    # Check if data is complete (no GSheet/KIS errors)
    has_gsheet_error = metadata.get("gsheet_error")
    has_kis_error = metadata.get("kis_error")

    if has_gsheet_error or has_kis_error:
        # Log which data source failed
        if has_gsheet_error:
            add_alert(f"[Data] GSheet error: {has_gsheet_error}", "WARN")
        if has_kis_error:
            add_alert(f"[Data] KIS error: {has_kis_error}", "WARN")
        add_alert("[Data] Portfolio loaded (partial - not cached)", "WARN")
        # Do NOT cache incomplete data
    else:
        # Cache only complete data
        set_portfolio_cache(result)
        add_alert("[Data] Portfolio loaded", "SUCCESS")
    logging.info("[DataService] Portfolio data cached successfully")

    return result


def convert_portfolio_to_account_format(portfolio: dict) -> dict:
    """
    Convert get_portfolio() output format to the format expected by print_account_info().

    Args:
        portfolio: Output from get_portfolio()

    Returns:
        dict in the format expected by print_account_info() in handle_account_info.py
    """
    if portfolio.get("error"):
        return portfolio

    merged = portfolio.get("merged_data", {})
    stats = portfolio.get("stats", {})
    exchange_rate = portfolio.get("exchange_rate", None)

    domestic_stocks = []
    overseas_stocks = []

    for ticker, info in merged.items():
        # Skip cash entries
        if info.get("type") == "CASH":
            continue

        currency = info.get("currency", "USD")
        qty = info.get("qty", 0)
        cur_price = info.get("cur_price", 0)
        total_investment = info.get("total_investment", 0)

        # Calculate avg_price and pnl
        avg_price = total_investment / qty if qty > 0 else 0
        current_value = qty * cur_price
        pnl_amt = current_value - total_investment
        pnl_rate = (pnl_amt / total_investment * 100) if total_investment > 0 else 0

        stock_data = {
            "name": info.get("name", "Unknown"),
            "qty": qty,
            "cur_price": cur_price,
            "avg_price": avg_price,
            "pnl_rate": pnl_rate,
            "pnl_amt": pnl_amt,
            "symbol": ticker
        }

        if currency == "KRW":
            domestic_stocks.append(stock_data)
        else:
            stock_data["exchange"] = "US"
            overseas_stocks.append(stock_data)

    return {
        "domestic_stocks": domestic_stocks,
        "overseas_stocks": overseas_stocks,
        "domestic_asset": {},
        "overseas_asset": {
            "frcr_drwg_psbl_amt_1": stats.get("us_cash_usd", 0)
        },
        "exchange_rate": exchange_rate,
        "krw_orderable": stats.get("kr_cash_krw", 0),
        "error": None
    }


def invalidate_cache() -> None:
    """
    Clear the portfolio cache.
    Call this when data is known to be stale (e.g., after placing an order).
    """
    clear_portfolio_cache()
    logging.info("[DataService] Portfolio cache invalidated")


def get_weight_diffs():
    """
    Calculate weight differences between current and target allocations.

    Returns:
        list: Sorted list of diffs (by abs_diff descending), each containing:
            ticker, name, cur_w, tgt_w, diff, abs_diff, qty_diff
    """
    import os

    portfolio_data = get_portfolio_data()
    merged_data = portfolio_data.get("merged_data", {})
    current_weights = portfolio_data.get("current_weights", {})
    targets = portfolio_data.get("targets", {})
    total_value_usd = portfolio_data.get("total_value_usd", 0.0)
    exchange_rate = portfolio_data.get("exchange_rate", None)

    # Load portfolio config to get group constituents
    config_path = os.path.join(os.path.expanduser("~"), "KIS_config", "portfolio_weights.json")
    constituents_set = set()
    main_ticker_constituents = {}  # main_ticker -> [constituents]

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        for group in config.get('groups', []):
            main_ticker = group.get('main_ticker')
            constituents = group.get('constituents', [])
            if main_ticker and constituents:
                constituents_set.update(constituents)
                main_ticker_constituents[main_ticker] = constituents
    except Exception as e:
        logging.warning(f"[get_weight_diffs] Failed to load config: {e}")

    # Merge constituents' current weight into main ticker
    merged_current_weights = dict(current_weights)
    for main_ticker, constituents in main_ticker_constituents.items():
        constituent_weight_sum = 0.0
        for c in constituents:
            if c in merged_current_weights:
                constituent_weight_sum += merged_current_weights.pop(c, 0.0)
        merged_current_weights[main_ticker] = merged_current_weights.get(main_ticker, 0.0) + constituent_weight_sum

    diffs = []

    # We care about all tickers in either Targets OR merged Current (excluding constituents)
    all_tickers = (set(merged_current_weights.keys()) | set(targets.keys())) - constituents_set

    for t in all_tickers:
        cur_w = merged_current_weights.get(t, 0.0)
        tgt_w = targets.get(t, 0.0)

        # Filter Cash
        data = merged_data.get(t, {})
        if data.get("type") == "CASH" or "cash" in t.lower() or "예수금" in t:
            continue

        diff = tgt_w - cur_w  # Target - Current
        name = data.get("name", t)

        # Calculate quantity diff
        val_diff_usd = diff * total_value_usd
        cur_price = data.get("cur_price", 0)
        currency = data.get("currency", "USD")

        # Fallback: Fetch price if not in portfolio
        if cur_price <= 0:
            try:
                # 1. Try WebSocket (fastest)
                try:
                    from strategy.raoeo import get_current_price
                    cur_price = get_current_price(t)
                except ImportError:
                    pass

                # 2. Determine market (KR vs US)
                from trading_config import get_stock_info
                stock_info = get_stock_info(t)
                is_kr = False
                if t.isdigit():
                    is_kr = True
                elif stock_info:
                    mkt = stock_info.get("market", "").upper()
                    if mkt in ["KOSPI", "KOSDAQ", "KONEX", "KRX"]:
                        is_kr = True

                # 3. Fetch from API if still 0
                if cur_price <= 0:
                    if is_kr:
                        from kis.kis_api.domestic_stock.inquire_price.inquire_price import inquire_price
                        from kis.kis_api import kis_auth as ka
                        env_dv = "demo" if ka.isPaperTrading() else "real"
                        # "J" is generic for KRX
                        df = inquire_price(env_dv, "J", t)
                        if df is not None and not df.empty and 'stck_prpr' in df.columns:
                            cur_price = float(df.iloc[0]['stck_prpr'])
                    else:
                        from kis.wrapper import fetch_price
                        cur_price = fetch_price(t)

                # 4. Set appropriate currency if fetching succeeded
                if cur_price > 0:
                    currency = "KRW" if is_kr else "USD"

            except Exception as e:
                logging.warning(f"Failed to fetch fallback price for {t}: {e}")

        qty_diff = 0
        if cur_price > 0:
            if currency == "KRW":
                val_diff_krw = val_diff_usd * exchange_rate
                qty_diff = val_diff_krw / cur_price
            else:
                qty_diff = val_diff_usd / cur_price

        diffs.append({
            "ticker": t,
            "name": name,
            "cur_w": cur_w,
            "tgt_w": tgt_w,
            "diff": diff,
            "abs_diff": abs(diff),
            "qty_diff": int(qty_diff)
        })

    # Sort by absolute difference descending
    diffs.sort(key=lambda x: x["abs_diff"], reverse=True)

    # Calculate cash weight info
    cash_info = {}
    try:
        from data.calculate_weights import get_cash_weight, load_config
        config_path = os.path.join(os.path.expanduser("~"), "KIS_config", "portfolio_weights.json")
        config = load_config(config_path)
        cash_strategy = config.get('cash_strategy', {'min': 0.1, 'mid': 0.2, 'max': 0.3})

        from utils import get_fear_and_greed
        fg_index = get_fear_and_greed()
        target_cash_weight = get_cash_weight(fg_index, cash_strategy)

        # Current cash weight
        current_cash = 0.0
        for t, data in merged_data.items():
            if data.get("type") == "CASH" or "cash" in t.lower():
                current_cash += data.get("current_value_usd", 0)
        current_cash_weight = current_cash / total_value_usd if total_value_usd > 0 else 0

        cash_info = {
            "current": current_cash_weight,
            "target": target_cash_weight,
            "diff": target_cash_weight - current_cash_weight
        }
    except Exception as e:
        logging.warning(f"[get_weight_diffs] Failed to calculate cash info: {e}")

    return diffs, total_value_usd, cash_info