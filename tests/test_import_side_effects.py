import os
import subprocess
import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"


def _run_import_check(tmp_path, code):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["PYTHONPATH"] = str(SRC_DIR)
    return subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_data_package_import_does_not_import_kis_data_service(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
import data
assert "data.data_service" not in sys.modules
assert "kis.kis_api.kis_auth" not in sys.modules
""",
    )

    assert result.returncode == 0, result.stderr


def test_telegram_package_import_does_not_initialize_bot_module(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
import telegram_bot
assert "telegram_bot.telegram_bot" not in sys.modules
""",
    )

    assert result.returncode == 0, result.stderr


def test_strategy_execution_import_does_not_touch_kis_config(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import pathlib
import strategy.execution_service
assert not (pathlib.Path.home() / "KIS_config").exists()
""",
    )

    assert result.returncode == 0, result.stderr
