import os
import json
import logging
from typing import Dict, Any, List, Union

# Config directory (same as kis_auth.py)
CONFIG_ROOT = os.path.join(os.path.expanduser("~"), "KIS_config")
STRATEGY_CONFIG_FILE = os.path.join(CONFIG_ROOT, "strategy_config.json")

def _load_config() -> Dict[str, Any]:
    """
    Internal function to load the unified strategy configuration.
    Returns an empty dict if file not found or invalid.
    """
    try:
        if not os.path.exists(STRATEGY_CONFIG_FILE):
            logging.error(f"Strategy config file not found: {STRATEGY_CONFIG_FILE}")
            return {}

        with open(STRATEGY_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in strategy config: {e}")
        return {}
    except Exception as e:
        logging.error(f"Failed to load strategy config: {e}")
        return {}

def get_strategy_config(strategy_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific strategy.

    Args:
        strategy_name: The name of the strategy key in config (e.g., 'raoeo', 'value_averaging')

    Returns:
        Dict containing the strategy's configuration, or empty dict if not found.
    """
    full_config = _load_config()
    return full_config.get(strategy_name, {})

def _get_history_file_path(strategy_name: str) -> str:
    """Get the file path for a strategy's history file."""
    return os.path.join(CONFIG_ROOT, f"{strategy_name}_history.json")

def load_history(strategy_name: str) -> Union[List, Dict]:
    """
    Load history data for a specific strategy.

    Args:
        strategy_name: 'raoeo' or 'value_averaging'

    Returns:
        List or Dict containing the history data, or empty container if not found.
    """
    file_path = _get_history_file_path(strategy_name)
    try:
        if not os.path.exists(file_path):
            return [] # Default to empty list, though some strategies might use dict

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load history for {strategy_name}: {e}")
        return []

def save_history(strategy_name: str, data: Union[List, Dict]) -> bool:
    """
    Save history data for a specific strategy.

    Args:
        strategy_name: 'raoeo' or 'value_averaging'
        data: The data to save

    Returns:
        True if successful, False otherwise.
    """
    file_path = _get_history_file_path(strategy_name)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Failed to save history for {strategy_name}: {e}")
        return False
