# -*- coding: utf-8 -*-
"""KIS API codes shared by trading and strategy modules."""

MARKET_KR = "KR"
MARKET_US = "US"

# Order Types - Overseas (US)
ORDER_TYPE_US_LIMIT = "00"
ORDER_TYPE_US_MOO = "31"
ORDER_TYPE_US_LOO = "32"
ORDER_TYPE_US_MOC = "33"
ORDER_TYPE_US_LOC = "34"

# Order Types - Domestic (KR)
ORDER_TYPE_KR_LIMIT = "00"
ORDER_TYPE_KR_MARKET = "01"

# Legacy/Generic Aliases (Use with caution)
ORDER_TYPE_LOC = ORDER_TYPE_US_LOC
ORDER_TYPE_LIMIT = ORDER_TYPE_US_LIMIT

EXCHANGE_CODE_MAP = {
    "NAS": "NASD",
    "NYS": "NYSE",
    "AMS": "AMEX",
}
