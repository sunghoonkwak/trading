"""
Common utility functions for the trading application.
"""
import sys
import unicodedata
import time
from datetime import datetime
import pandas as pd
import logging

try:
    import fear_and_greed
    FG_AVAILABLE = True
except ImportError:
    fear_and_greed = None
    FG_AVAILABLE = False
    logging.warning("fear_and_greed not found. F&G index will use default value.")

try:
    import pandas_market_calendars as mcal
except ImportError:
    mcal = None
    logging.warning("pandas_market_calendars not found. Holiday check will be disabled.")

# Cache for Fear & Greed Index
_fg_cache = {"value": 50, "last_update": 0}


def get_fear_and_greed() -> float:
    """
    Fetches Fear & Greed index safely with caching (10 min).
    Prevents blocking with frequent network calls.

    Returns:
        float: Current F&G index value (0-100). Default 50 on error.
    """
    global _fg_cache

    if not FG_AVAILABLE:
        return 50.0

    try:
        now = time.time()
        # Update every 10 minutes (600 seconds) to avoid API spam/blocking
        if now - _fg_cache["last_update"] > 600:
            data = fear_and_greed.get()
            _fg_cache["value"] = float(data.value)
            _fg_cache["last_update"] = now
    except Exception as e:
        logging.warning(f"Failed to fetch F&G index: {e}")
        # Retain old value on error
        pass

    return _fg_cache["value"]

# Platform-specific getch implementation
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import msvcrt

    def getch() -> bytes:
        """Read a single keypress from the terminal (Windows)."""
        return msvcrt.getch()

    def getch_str() -> str:
        """Read a single keypress and return as string (Windows)."""
        return msvcrt.getch().decode('utf-8', errors='ignore')
else:
    import tty
    import termios

    def getch() -> bytes:
        """Read a single keypress from the terminal (Linux/Mac)."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            return ch.encode('utf-8')
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def getch_str() -> str:
        """Read a single keypress and return as string (Linux/Mac)."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def get_fixed_width(text: str, width: int = 8) -> str:
    """
    Get fixed-width display text for CJK characters.

    Args:
        text: The string to format.
        width: The target display width.

    Returns:
        A string formatted to the specified width, with padding if necessary.
    """
    current_width = 0
    result = ""
    for char in text:
        w = 2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
        if current_width + w > width:
            break
        result += char
        current_width += w
    return result + (" " * (width - current_width))


def safe_cast(val, to_type, default=None):
    """
    Safely cast a value to a specific type.

    Args:
        val: The value to cast.
        to_type: The type to cast to (e.g., int, float).
        default: The default value to return if casting fails.

    Returns:
        The cast value or the default value.
    """
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default


def format_number(val, default="0") -> str:
    """
    Format a numeric value with thousands separators.

    Handles both integer and decimal values. Skips formatting if
    value already contains $ or comma.

    Args:
        val: The price value to format (str, int, or float).
        default: The default string to return if formatting fails.

    Returns:
        Formatted string (e.g., "53,900" or "57.32").
    """
    price_str = str(val).strip()

    # Skip if already formatted or contains currency symbol
    if '$' in price_str or ',' in price_str or not price_str:
        return price_str if price_str else default

    try:
        price_val = float(price_str)
        if price_val == int(price_val):
            return f"{int(price_val):,}"
        else:
            return f"{price_val:,.2f}"
    except (ValueError, TypeError):
        return default


def is_market_holiday(name="NYSE", date=None) -> bool:
    """
    Check if the specified market is on holiday on the given date.

    Args:
        name: Market name (e.g., 'NYSE', 'NASDAQ'). Default is 'NYSE'.
        date: datetime object or str(YYYYMMDD). Default is current UTC time.

    Returns:
        True if it's a holiday or weekend, False otherwise.
    """
    if mcal is None:
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
        logging.error(f"Error checking {name} holiday: {e}")
        return False
