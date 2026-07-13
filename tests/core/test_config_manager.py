import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from infrastructure import config


def test_config_manager_returns_default_for_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CONFIG_ROOT", str(tmp_path))

    assert config.load_json(config.ConfigFile.MEMO, default=[]) == []


def test_config_manager_preserves_read_only_files(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CONFIG_ROOT", str(tmp_path))

    with pytest.raises(ValueError, match="read-only"):
        config.save_json(config.ConfigFile.STRATEGY_CONFIG, {})
