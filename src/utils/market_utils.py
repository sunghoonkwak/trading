# -*- coding: utf-8 -*-
"""
Market Utilities Module

Provides helper functions for market indicators (Fear & Greed) and calendar (holidays).
"""
import time
import logging
from datetime import datetime
from typing import Optional

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

def is_market_holiday(name: str = "NYSE", date: Optional[datetime] = None) -> bool:
    """
    Check if the specified market is on holiday on the given date.
    """
    if mcal is None:
        logging.warning("[MarketUtils] pandas_market_calendars not found. Holiday check disabled.")
        return False

    if date is None:
        date = datetime.utcnow()
    elif isinstance(date, str):
        try:
            date = datetime.strptime(date, "%Y%m%d")
        except ValueError:
            return False

    try:
        cal = mcal.get_calendar(name)
        schedule = cal.schedule(start_date=date, end_date=date)
        return schedule.empty
    except Exception as e:
        logging.error(f"[MarketUtils] Error checking {name} holiday: {e}")
        return False
