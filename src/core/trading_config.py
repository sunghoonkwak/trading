import os
import json

from core.constants import ENV_FALSE_VALUES, ENV_TRUE_VALUES

_DEFAULT_KIS_US_MARKET = ("NAS", "DNAS")
_KIS_US_MARKETS = {
    "NASDAQ": _DEFAULT_KIS_US_MARKET,
    "NAS": _DEFAULT_KIS_US_MARKET,
    "NYSE": ("NYS", "DNYS"),
    "NYS": ("NYS", "DNYS"),
    "AMEX": ("AMS", "DAMS"),
    "AMS": ("AMS", "DAMS"),
}
_KIS_MARKET_PREFIXES = tuple(
    dict.fromkeys(prefix for _, prefix in _KIS_US_MARKETS.values())
)


def _env_value(name: str) -> str:
    return os.getenv(name, "").strip().lower()


def is_kis_rest_api_enabled() -> bool:
    """Return whether KIS REST API surfaces are enabled."""
    return _env_value("KIS_ENABLE_REST_API") not in ENV_FALSE_VALUES


def is_kis_domestic_enabled() -> bool:
    """Return whether KIS domestic-stock account/order surfaces are enabled."""
    return _env_value("KIS_ENABLE_DOMESTIC") in ENV_TRUE_VALUES


def _kis_market_codes(market: str) -> tuple[str, str]:
    return _KIS_US_MARKETS.get(market.upper(), _DEFAULT_KIS_US_MARKET)


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
    for prefix in _KIS_MARKET_PREFIXES:
        if ticker.startswith(prefix):
            return ticker[len(prefix):]
    return ticker


def get_stock_info(ticker: str) -> dict:
    """Find stock information by ticker across all markets, handling prefixes."""
    if not ticker:
        return {}

    clean_ticker = strip_market_prefix(ticker).strip()

    for market in ["KR", "US"]:
        for stock in CONFIG.get(market, []):
            if stock.get("ticker") == clean_ticker:
                return stock
    return {}


def update_stock_name(ticker: str, new_name: str):
    """Update the 'name' field for a ticker in CONFIG and save to JSON if changed."""
    if not ticker or not new_name:
        return

    clean_ticker = strip_market_prefix(ticker).strip()
    changed = False

    for market in ["KR", "US"]:
        for stock in CONFIG.get(market, []):
            if stock.get("ticker") == clean_ticker:
                if stock.get("name") == new_name:
                    break
                stock["name"] = new_name
                changed = True
                break
        if changed:
            break

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
    if not stock:
        return "NAS"

    exchange_code, _ = _kis_market_codes(stock.get("market", "NASDAQ"))
    return exchange_code


def get_kis_market_prefix(ticker: str) -> str:
    """Get KIS market prefix (DNAS, DNYS, DAMS) for a US ticker from CONFIG."""
    # If already has prefix, return as is
    for prefix in _KIS_MARKET_PREFIXES:
        if ticker.startswith(prefix):
            return ticker

    stock = get_stock_info(ticker)
    if not stock:
        return f"DNAS{ticker}"

    _, prefix = _kis_market_codes(stock.get("market", "NASDAQ"))
    return f"{prefix}{ticker}"
