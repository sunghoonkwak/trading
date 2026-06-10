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


def test_data_portfolio_cache_export_stays_lightweight(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
from data import PortfolioCache
assert PortfolioCache.__name__ == "PortfolioCache"
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


def test_broker_package_import_does_not_touch_kis_config(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import pathlib
import broker.kis_broker
assert not (pathlib.Path.home() / "KIS_config").exists()
""",
    )

    assert result.returncode == 0, result.stderr


def test_app_imports_do_not_load_runtime_kis_modules(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
import core.web_server
import scheduler.scheduler_order
import telegram_bot.telegram_strategy
assert "kis.kis_api.kis_auth" not in sys.modules
""",
    )

    assert result.returncode == 0, result.stderr


def test_scheduler_portfolio_import_does_not_load_legacy_portfolio_wrapper(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
import scheduler.scheduler_portfolio
assert "kis.get_portfolio" not in sys.modules
""",
    )

    assert result.returncode == 0, result.stderr


def test_data_service_import_does_not_load_kis_worker_from_kis_package(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
import data.data_service
assert "kis.kis_thread" not in sys.modules
""",
    )

    assert result.returncode == 0, result.stderr


def test_kis_package_does_not_contain_app_websocket_policy_files():
    assert not (SRC_DIR / "kis" / "event_handler.py").exists()
    assert not (SRC_DIR / "kis" / "ws_notifications.py").exists()
    assert not (SRC_DIR / "kis" / "rest_client.py").exists()
    assert not (SRC_DIR / "kis" / "ws_manager.py").exists()
    assert not (SRC_DIR / "kis" / "event_pipe.py").exists()
