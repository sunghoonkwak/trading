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
    print(f"[Config] Error loading stock_configuration.json: {e}")

def strip_market_prefix(ticker: str) -> str:
    """Remove market prefix (DNAS, DNYS, DAMS) from overseas stock code for display."""
    if not ticker:
        return ticker
    for prefix in ["DNAS", "DNYS", "DAMS"]:
        if ticker.startswith(prefix):
            return ticker[len(prefix):]
    return ticker


def get_stock_info(ticker: str) -> dict:
    """Find stock information by ticker across all markets, handling prefixes."""
    if not ticker: return {}

    # Strip known market prefixes (DNAS: Nasdaq, DNYS: NYSE, DAMS: AMEX, etc.)
    clean_ticker = ticker
    for prefix in ["DNAS", "DNYS", "DAMS"]:
        if ticker.startswith(prefix):
            clean_ticker = ticker[len(prefix):]
            break

    clean_ticker = clean_ticker.strip()

    for market in ["KR", "US"]:
        for stock in CONFIG.get(market, []):
            if stock.get("ticker") == clean_ticker:
                return stock
    return {}
def update_stock_name(ticker: str, new_name: str):
    """Update the 'name' field for a ticker in CONFIG and save to JSON if changed."""
    if not ticker or not new_name: return

    clean_ticker = strip_market_prefix(ticker).strip()
    changed = False

    for market in ["KR", "US"]:
        for stock in CONFIG.get(market, []):
            if stock.get("ticker") == clean_ticker:
                if stock.get("name") != new_name:
                    stock["name"] = new_name
                    changed = True
                break
        if changed: break

    if changed:
        try:
            _json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_configuration.json")
            with open(_json_path, "w", encoding="utf-8") as f:
                json.dump(CONFIG, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Error saving stock_configuration.json: {e}")
