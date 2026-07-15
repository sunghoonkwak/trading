"""File-backed configuration adapter."""

import json
import logging
import os
import tempfile
from enum import Enum
from typing import Any, Dict, Union

from infrastructure.runtime_settings import CONFIG_ROOT


class ConfigFile(Enum):
    PORTFOLIO = ("portfolio.json", False)
    MEMO = ("memo.json", False)
    STRATEGY_HISTORY = ("strategy_history.json", False)
    STRATEGY_CONFIG = ("strategy_config.json", True)
    PORTFOLIO_WEIGHTS = ("portfolio_weights.json", True)

    @property
    def filename(self) -> str:
        return self.value[0]

    @property
    def read_only(self) -> bool:
        return self.value[1]


def _get_config_path(file_type: ConfigFile) -> str:
    return os.path.join(CONFIG_ROOT, file_type.filename)


def load_json(
    file_type: ConfigFile,
    default: Any = None,
    *,
    strict: bool = False,
) -> Union[Dict, list]:
    path = _get_config_path(file_type)
    if default is None:
        default = {}
    try:
        if not os.path.exists(path):
            logging.warning(f"[ConfigManager] File not found: {path}")
            return default
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as error:
        logging.error(f"[ConfigManager] Failed to load {file_type.filename}: {error}")
        if strict:
            raise
        return default


def save_json(file_type: ConfigFile, data: Any) -> bool:
    if file_type.read_only:
        raise ValueError(f"File {file_type.name} is read-only.")
    path = _get_config_path(file_type)
    temp_path = None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=os.path.dirname(path),
            prefix=f".{file_type.filename}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temp_path = file.name
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
        directory_fd = os.open(os.path.dirname(path), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return True
    except Exception as error:
        logging.error(f"[ConfigManager] Failed to save {file_type.filename}: {error}")
        return False
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
