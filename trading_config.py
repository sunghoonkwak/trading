import os
import json

# Load Stock Configuration from JSON
CONFIG = {}

try:
    _json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_configuration.json")
    if os.path.exists(_json_path):
        with open(_json_path, "r", encoding="utf-8") as f:
            CONFIG = json.load(f)
except Exception as e:
    pass

def get_stock_info(ticker: str) -> dict:
    """Find stock information by ticker across all markets, handling prefixes."""
    if not ticker: return {}

    # Strip known market prefixes (DNAS: Nasdaq, DNYE: NYSE, etc.)
    clean_ticker = ticker
    for prefix in ["DNAS", "DNYE", "DAMS", "BAQ", "BAY"]:
        if ticker.startswith(prefix):
            clean_ticker = ticker[len(prefix):]
            break

    for market in ["KR", "US"]:
        for stock in CONFIG.get(market, []):
            if stock.get("ticker") == clean_ticker:
                return stock
    return {}
