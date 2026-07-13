# -*- coding: utf-8 -*-
"""External market-calendar and sentiment adapter."""

import logging
import time
from datetime import datetime
from datetime import time as dt_time
from typing import Dict, Optional, Union, cast

import pytz

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


_fg_cache = {"value": 50.0, "last_update": 0.0}


def get_us_market_status(date: Optional[Union[str, datetime]] = None) -> Dict:
    """Return the established US trading-window status mapping."""
    tz_et = pytz.timezone("US/Eastern")
    now_et = datetime.now(tz_et)
    check_date = date or now_et
    if isinstance(check_date, str):
        date_text = check_date
        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(date_text, fmt)
                check_date = tz_et.localize(parsed.replace(
                    hour=now_et.hour,
                    minute=now_et.minute,
                    second=now_et.second,
                ))
                break
            except ValueError:
                continue
    check_datetime = cast(datetime, check_date)
    if check_datetime.weekday() >= 5:
        return {"is_market_open": False, "message": "Market closed (Weekend)"}
    if not _has_market_session("NYSE", check_datetime):
        return {"is_market_open": False, "message": "Market closed (Holiday)"}
    current_time = now_et.time()
    start_time = dt_time(5, 0)
    end_time = dt_time(16, 0)
    if start_time <= current_time <= end_time:
        return {"is_market_open": True, "message": "Trading Allowed"}
    return {
        "is_market_open": False,
        "message": f"Trading not allowed (Current ET: {now_et.strftime('%H:%M')})",
    }


def get_fear_and_greed() -> float:
    """Fetch the external Fear & Greed index with its existing cache policy."""
    global _fg_cache
    if not FG_AVAILABLE:
        return 50.0
    try:
        now = time.time()
        if now - _fg_cache["last_update"] > 600:
            data = fear_and_greed.get()
            _fg_cache["value"] = float(data.value)
            _fg_cache["last_update"] = now
    except Exception as error:
        logging.warning("[MarketUtils] Failed to fetch F&G index: %s", error)
    return _fg_cache["value"]


def _has_market_session(name: str = "NYSE", date: Optional[datetime] = None) -> bool:
    if mcal is None:
        logging.warning(
            "[MarketUtils] pandas_market_calendars not found. "
            "Market session check disabled."
        )
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
            return True
    try:
        calendar = mcal.get_calendar(name)
        schedule = calendar.schedule(start_date=date, end_date=date)
        return not schedule.empty
    except Exception as error:
        logging.error("[MarketUtils] Error checking %s market session: %s", name, error)
        return True
