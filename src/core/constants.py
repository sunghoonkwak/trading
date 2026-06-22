# -*- coding: utf-8 -*-
"""
Global Constants Module

Application-wide runtime defaults shared across packages.
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
# Market Defaults
# =============================================================================
DEFAULT_USD_KRW_EXCHANGE_RATE = 1500.0

# =============================================================================
# Timeouts & Durations (in seconds)
# =============================================================================
API_TIMEOUT_SHORT = 30.0
API_TIMEOUT_LONG = 60.0
PORTFOLIO_CACHE_EXPIRE = 300
MARKET_STATE_SAVE_INTERVAL = 60
