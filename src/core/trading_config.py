import os
import json

# Load Stock Configuration from JSON
CONFIG = {}

try:
    # Look for the config file in the parent 'src' directory
    _src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _json_path = os.path.join(_src_dir, "stock_configuration.json")
    
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
            # Use the already calculated _json_path to save changes
            with open(_json_path, "w", encoding="utf-8") as f:
                json.dump(CONFIG, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Error saving stock_configuration.json: {e}")

def get_kis_exchange_code(ticker: str) -> str:
    """Get KIS exchange code (NAS, NYS, AMS) for a US ticker from CONFIG."""
    stock = get_stock_info(ticker)
    if not stock: return "NAS"

    market = stock.get("market", "NASDAQ").upper()
    market_to_excd = {
        "NASDAQ": "NAS", "NYSE": "NYS", "AMEX": "AMS",
        "NAS": "NAS", "NYS": "NYS", "AMS": "AMS"
    }
    return market_to_excd.get(market, "NAS")

def get_kis_market_prefix(ticker: str) -> str:
    """Get KIS market prefix (DNAS, DNYS, DAMS) for a US ticker from CONFIG."""
    # If already has prefix, return as is
    for prefix in ["DNAS", "DNYS", "DAMS"]:
        if ticker.startswith(prefix):
            return ticker

    stock = get_stock_info(ticker)
    if not stock: return f"DNAS{ticker}"

    market = stock.get("market", "NASDAQ").upper()
    market_to_prefix = {
        "NASDAQ": "DNAS", "NYSE": "DNYS", "AMEX": "DAMS",
        "NAS": "DNAS", "NYS": "DNYS", "AMS": "DAMS"
    }
    prefix = market_to_prefix.get(market, "DNAS")
    return f"{prefix}{ticker}"
