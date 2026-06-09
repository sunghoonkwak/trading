# -*- coding: utf-8 -*-
"""Strategy policy defaults shared by strategy modules."""

DEFAULT_FEAR_GREED = 50.0
DEFAULT_VA_THRESHOLD = 0.15
DEFAULT_RAOEO_PROFIT = 0.10
DEFAULT_REBALANCE_THRESHOLD = 0.05

# KIS rejects buy orders exceeding 30% above current price.
# Use 25% cap as a safety margin.
MAX_BUY_PRICE_RATIO = 1.25
