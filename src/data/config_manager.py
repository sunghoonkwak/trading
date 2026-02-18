# -*- coding: utf-8 -*-
"""
Configuration Manager Module

Handles loading and saving of JSON configuration and history files.
"""
import os
import json
import logging
from enum import Enum
from typing import Any, Dict, Union

from core.constants import CONFIG_ROOT

class ConfigFile(Enum):
    """
    Enum for configuration and history files.
    Value is a tuple of (filename, read_only).
    """
    PORTFOLIO = ("portfolio.json", False)
    MEMO = ("memo.json", False)
    VA_HISTORY = ("value_averaging_history.json", False)
    RAOEO_HISTORY = ("raoeo_history.json", False)
    REBALANCING_HISTORY = ("rebalancing_history.json", False)
    STRATEGY_CONFIG = ("strategy_config.json", True)
    PORTFOLIO_WEIGHTS = ("portfolio_weights.json", True)

    @property
    def filename(self) -> str:
        return self.value[0]

    @property
    def read_only(self) -> bool:
        return self.value[1]

def _get_config_path(file_type: ConfigFile) -> str:
    """Get full absolute path for a config file."""
    return os.path.join(CONFIG_ROOT, file_type.filename)

def load_json(file_type: ConfigFile, default: Any = None) -> Union[Dict, list]:
    """Load JSON data from a config file."""
    path = _get_config_path(file_type)
    if default is None:
        default = {}

    try:
        if not os.path.exists(path):
            logging.warning(f"[ConfigManager] File not found: {path}")
            return default

        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"[ConfigManager] Failed to load {file_type.filename}: {e}")
        return default

def save_json(file_type: ConfigFile, data: Any) -> bool:
    """Save data to a JSON config file."""
    if file_type.read_only:
        raise ValueError(f"File {file_type.name} is read-only.")

    path = _get_config_path(file_type)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"[ConfigManager] Failed to save {file_type.filename}: {e}")
        return False
