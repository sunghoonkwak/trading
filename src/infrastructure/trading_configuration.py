"""Stock metadata, KIS market mapping, and feature-flag adapter."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from infrastructure.runtime_settings import ENV_FALSE_VALUES, ENV_TRUE_VALUES

STOCK_CONFIGURATION_PATH = Path(__file__).resolve().parent / "stock_configuration.json"


def load_stock_configuration() -> dict[str, Any]:
    try:
        with STOCK_CONFIGURATION_PATH.open(encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        logging.warning("Failed to load stock_configuration.json: file not found")
    except Exception as error:
        logging.warning("Failed to load stock_configuration.json: %s", error)
    return {}


def save_stock_configuration(configuration: dict[str, Any]) -> None:
    try:
        with STOCK_CONFIGURATION_PATH.open("w", encoding="utf-8") as file:
            json.dump(configuration, file, indent=4, ensure_ascii=False)
    except Exception as error:
        logging.warning("Failed to save stock_configuration.json: %s", error)


_DEFAULT_KIS_US_MARKET = ("NAS", "DNAS")
_KIS_US_MARKETS = {"NASDAQ": _DEFAULT_KIS_US_MARKET, "NAS": _DEFAULT_KIS_US_MARKET,
                   "NYSE": ("NYS", "DNYS"), "NYS": ("NYS", "DNYS"),
                   "AMEX": ("AMS", "DAMS"), "AMS": ("AMS", "DAMS")}
_KIS_MARKET_PREFIXES = tuple(dict.fromkeys(prefix for _, prefix in _KIS_US_MARKETS.values()))
CONFIG = load_stock_configuration()


def _env_value(name: str) -> str:
    return os.getenv(name, "").strip().lower()


def is_kis_rest_api_enabled() -> bool:
    return _env_value("KIS_ENABLE_REST_API") not in ENV_FALSE_VALUES


def is_kis_domestic_enabled() -> bool:
    return _env_value("KIS_ENABLE_DOMESTIC") in ENV_TRUE_VALUES


def strip_market_prefix(ticker: str) -> str:
    for prefix in _KIS_MARKET_PREFIXES:
        if ticker.startswith(prefix):
            return ticker[len(prefix):]
    return ticker


def get_stock_info(ticker: str) -> dict:
    clean_ticker = strip_market_prefix(ticker).strip()
    for market in ["KR", "US"]:
        for stock in CONFIG.get(market, []):
            if stock.get("ticker") == clean_ticker:
                return stock
    return {}


def update_stock_name(ticker: str, new_name: str) -> None:
    stock = get_stock_info(ticker)
    if stock and new_name and stock.get("name") != new_name:
        stock["name"] = new_name
        save_stock_configuration(CONFIG)


def get_kis_exchange_code(ticker: str) -> str:
    return _KIS_US_MARKETS.get(get_stock_info(ticker).get("market", "NASDAQ").upper(), _DEFAULT_KIS_US_MARKET)[0]


def get_kis_market_prefix(ticker: str) -> str:
    if any(ticker.startswith(prefix) for prefix in _KIS_MARKET_PREFIXES):
        return ticker
    return _KIS_US_MARKETS.get(get_stock_info(ticker).get("market", "NASDAQ").upper(), _DEFAULT_KIS_US_MARKET)[1] + ticker
