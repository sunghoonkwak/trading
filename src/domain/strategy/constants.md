# Strategy constants

`constants.py` contains domain strategy fallbacks and broker-independent order
intent values such as `LIMIT` and `LOC`. It also owns RAOEO buy-price safety
limits and the US/Eastern history date formats used by strategy calculations.

Configuration may override thresholds, but should use these constants as its
explicit fallback values.
