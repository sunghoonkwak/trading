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


def safe_int_format(val, default="0") -> str:
    """
    Safely format a value as an integer string with thousands separators.

    Args:
        val: The value to format.
        default: The default string to return if formatting fails.

    Returns:
        Formatted string (e.g., "1,234") or default.
    """
    try:
        if not val or str(val).strip() == "":
            return default
        # Handle cases where val might be a float string like "1234.56"
        return format(int(float(val)), ",")
    except (ValueError, TypeError):
        return default
