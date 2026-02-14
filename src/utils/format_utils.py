# -*- coding: utf-8 -*-
"""
Formatting Utilities Module

Helper functions for text and number formatting.
"""
import unicodedata
from typing import Any

def get_fixed_width(text: str, width: int = 8) -> str:
    """Get fixed-width display text for CJK characters."""
    current_width = 0
    result = ""
    for char in text:
        w = 2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
        if current_width + w > width:
            break
        result += char
        current_width += w
    return result + (" " * (width - current_width))

def safe_cast(val: Any, to_type: type, default: Any = None) -> Any:
    """Safely cast a value to a specific type."""
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default

def format_number(val: Any, default: str = "0") -> str:
    """Format a numeric value with thousands separators."""
    price_str = str(val).strip()
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
