# -*- coding: utf-8 -*-
"""
Global Constants Module

Centralized storage for all magic numbers, fixed strings, and configuration defaults.
"""
import os

# =============================================================================
# System Paths
# =============================================================================
CONFIG_ROOT = os.path.join(os.path.expanduser("~"), "KIS_config")

# =============================================================================
# Network Settings
# =============================================================================
DEFAULT_HOST = "0.0.0.0"
DEFAULT_WEB_PORT = 8080

# =============================================================================
# Timeouts & Durations (in seconds)
# =============================================================================
API_TIMEOUT_SHORT = 30.0
API_TIMEOUT_LONG = 60.0
PORTFOLIO_CACHE_EXPIRE = 300
MARKET_STATE_SAVE_INTERVAL = 60

# =============================================================================
# Exchange & Order Codes (KIS Specific)
# =============================================================================
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

# Exchange Code Mapping
EXCHANGE_CODE_MAP = {
    "NAS": "NASD",
    "NYS": "NYSE",
    "AMS": "AMEX"
}

# =============================================================================
# Strategy Specifics
# =============================================================================
DEFAULT_FEAR_GREED = 50.0
DEFAULT_VA_THRESHOLD = 0.15
DEFAULT_RAOEO_PROFIT = 0.10
