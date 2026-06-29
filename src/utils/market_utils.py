# -*- coding: utf-8 -*-
"""
Market Utilities Module

Provides helper functions for market indicators and market calendar status.
"""
import time
import logging
from datetime import datetime, time as dt_time
from typing import Dict, Optional, Union
import pytz

# Optional external dependencies
try:
    import fear_and_greed
    FG_AVAILABLE = True
except ImportError:
    fear_and_greed = None
    FG_AVAILABLE = False

try:
    import pandas_market_calendars as mcal
except ImportError:
    mcal = None

# Internal cache for Fear & Greed Index
_fg_cache = {"value": 50.0, "last_update": 0.0}

def get_us_market_status(date: Optional[Union[str, datetime]] = None) -> Dict:
    """
    Checks if current time is within allowed US trading hours (05:00 - 16:00 ET).
    Returns { "is_market_open": bool, "message": str }.
    """
    tz_et = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_et)
    check_date = date or now_et
    if isinstance(check_date, str):
        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(check_date, fmt)
                check_date = tz_et.localize(parsed.replace(
                    hour=now_et.hour,
                    minute=now_et.minute,
                    second=now_et.second,
                ))
                break
            except ValueError:
                continue

    # Check weekend
    if check_date.weekday() >= 5:
        return {
            "is_market_open": False,
            "message": "Market closed (Weekend)",
        }

    if not _has_market_session("NYSE", check_date):
        return {
            "is_market_open": False,
            "message": "Market closed (Holiday)",
        }

    current_time = now_et.time()
    start_time = dt_time(5, 0)  # 05:00 ET
    end_time = dt_time(16, 0)    # 16:00 ET

    if start_time <= current_time <= end_time:
        return {
            "is_market_open": True,
            "message": "Trading Allowed",
        }
    return {
        "is_market_open": False,
        "message": f"Trading not allowed (Current ET: {now_et.strftime('%H:%M')})",
    }

def get_fear_and_greed() -> float:
    """
    Fetches Fear & Greed index with caching (10 min duration).
    """
    global _fg_cache
    if not FG_AVAILABLE:
        return 50.0

    try:
        now = time.time()
        # Update every 10 minutes (600 seconds)
        if now - _fg_cache["last_update"] > 600:
            data = fear_and_greed.get()
            _fg_cache["value"] = float(data.value)
            _fg_cache["last_update"] = now
    except Exception as e:
        logging.warning(f"[MarketUtils] Failed to fetch F&G index: {e}")

    return _fg_cache["value"]

def _has_market_session(name: str = "NYSE", date: Optional[datetime] = None) -> bool:
    """
    Check if the specified market has a trading session on the given date.
    """
    if mcal is None:
        logging.warning("[MarketUtils] pandas_market_calendars not found. Market session check disabled.")
        return True

    if date is None:
        date = datetime.utcnow()
    elif isinstance(date, str):
        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                date = datetime.strptime(date, fmt)
                break
            except ValueError:
                continue
        if isinstance(date, str):
            # Failed to parse
            return True

    try:
        cal = mcal.get_calendar(name)
        schedule = cal.schedule(start_date=date, end_date=date)
        return not schedule.empty
    except Exception as e:
        logging.error(f"[MarketUtils] Error checking {name} market session: {e}")
        return True
