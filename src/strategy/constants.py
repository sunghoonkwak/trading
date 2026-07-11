"""Compatibility exports for strategy policy defaults."""

import pytz

TZ_ET = pytz.timezone("US/Eastern")

__all__ = [name for name in globals() if name.isupper()]
