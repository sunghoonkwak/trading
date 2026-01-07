"""
Common utility functions for the trading application.
"""
import unicodedata

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
