"""Dependency-free text and number formatting for infrastructure output."""

import unicodedata
from typing import Any


def get_fixed_width(text: str, width: int = 8) -> str:
    """Return CJK-aware text padded or truncated to a display width."""
    current_width = 0
    result = ""
    for char in text:
        char_width = 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
        if current_width + char_width > width:
            break
        result += char
        current_width += char_width
    return result + (" " * (width - current_width))


def format_number(value: Any, default: str = "0") -> str:
    """Format a numeric value with thousands separators."""
    text = str(value).strip()
    if "$" in text or "," in text or not text:
        return text or default
    try:
        number = float(text)
    except (TypeError, ValueError):
        return default
    if number == int(number):
        return f"{int(number):,}"
    return f"{number:,.2f}"
