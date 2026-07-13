"""Adapter for the repository stock-configuration file."""

import json
import logging
from pathlib import Path
from typing import Any

STOCK_CONFIGURATION_PATH = Path(__file__).resolve().parents[1] / "stock_configuration.json"


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
