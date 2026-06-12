import sys
import unittest
from pathlib import Path

from cryptography.fernet import Fernet


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class CredentialsTest(unittest.TestCase):
    def test_load_credentials_reads_kis_and_toss_values(self):
        from core.credentials import (
            generate_key_from_password,
            load_credentials,
        )

        config_root = ROOT / "tests" / ".tmp-credentials"
        self.addCleanup(lambda: self._remove_tree(config_root))
        config_root.mkdir(exist_ok=True)
        (config_root / "password.txt").write_text("test-password\n", encoding="utf-8")

        fernet = Fernet(generate_key_from_password("test-password"))
        encrypted = fernet.encrypt(
            b"kis-key,kis-secret,hts-id,toss-client-id,toss-client-secret"
        )
        (config_root / "credentials.enc").write_bytes(encrypted)

        credentials = load_credentials(config_root=config_root)

        self.assertEqual(credentials.kis_app_key, "kis-key")
        self.assertEqual(credentials.kis_app_secret, "kis-secret")
        self.assertEqual(credentials.kis_hts_id, "hts-id")
        self.assertEqual(credentials.toss_client_id, "toss-client-id")
        self.assertEqual(credentials.toss_client_secret, "toss-client-secret")

    def test_legacy_kis_credentials_keep_toss_values_empty(self):
        from core.credentials import (
            generate_key_from_password,
            load_credentials,
        )

        config_root = ROOT / "tests" / ".tmp-legacy-credentials"
        self.addCleanup(lambda: self._remove_tree(config_root))
        config_root.mkdir(exist_ok=True)
        (config_root / "password.txt").write_text("test-password\n", encoding="utf-8")

        fernet = Fernet(generate_key_from_password("test-password"))
        (config_root / "credentials.enc").write_bytes(
            fernet.encrypt(b"kis-key,kis-secret,hts-id")
        )

        credentials = load_credentials(config_root=config_root)

        self.assertEqual(credentials.kis_app_key, "kis-key")
        self.assertEqual(credentials.kis_app_secret, "kis-secret")
        self.assertEqual(credentials.kis_hts_id, "hts-id")
        self.assertEqual(credentials.toss_client_id, "")
        self.assertEqual(credentials.toss_client_secret, "")

    def _remove_tree(self, path):
        if not path.exists():
            return
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import validate_config


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _stock_config():
    return {
        "US": [
            {"ticker": "SOXL", "name": "Direxion Daily SOXL", "market": "AMS"},
            {"ticker": "TLTW", "name": "iShares TLTW", "market": "AMS"},
        ],
        "KR": [
            {"ticker": "005930", "name": "Samsung Electronics", "market": "KOSPI"},
        ],
    }


def _strategy_config():
    return {
        "cash_ticker": "TLTW",
        "raoeo": {
            "enabled": True,
            "targets": {
                "SOXL": {
                    "enabled": True,
                    "seed": 20000,
                    "duration": 40,
                    "phase": [
                        {
                            "name": "Phase 0",
                            "threshold": 0.1,
                            "buy": [
                                {
                                    "type": "normal",
                                    "ratio": 1,
                                    "price_percent_cap": 0.1,
                                },
                                {
                                    "type": "filling",
                                    "target_ratio": 0.1,
                                    "price_percent_cap": -0.05,
                                },
                            ],
                            "sell": [
                                {"type": "LOC", "ratio": 0.5, "profit": 0.2},
                                {"type": "Limit", "ratio": 0.5, "profit": 0.2},
                            ],
                        },
                        {
                            "name": "Phase 1",
                            "threshold": 0.2,
                            "buy": [{"type": "normal", "ratio": 1}],
                            "sell": [{"type": "LOC", "ratio": 1, "profit": 0.1}],
                        },
                        {
                            "name": "Fallback",
                            "buy": [{"type": "average", "ratio": 1}],
                            "sell": [{"type": "Limit", "ratio": 1, "profit": 0.1}],
                        },
                    ],
                }
            },
        },
    }


def test_reports_unknown_enabled_raoeo_ticker():
    config = _strategy_config()
    config["raoeo"]["targets"]["MISSING"] = config["raoeo"]["targets"].pop("SOXL")

    errors = validate_config.validate_strategy_config(config, _stock_config())

    assert any("MISSING" in error and "stock_configuration" in error for error in errors)


def test_reports_non_positive_seed_and_duration():
    config = _strategy_config()
    target = config["raoeo"]["targets"]["SOXL"]
    target["seed"] = 0
    target["duration"] = -1

    errors = validate_config.validate_strategy_config(config, _stock_config())

    assert any("SOXL.seed" in error for error in errors)
    assert any("SOXL.duration" in error for error in errors)


def test_reports_thresholds_that_are_not_ascending():
    config = _strategy_config()
    phases = config["raoeo"]["targets"]["SOXL"]["phase"]
    phases[0]["threshold"] = 0.3
    phases[1]["threshold"] = 0.2

    errors = validate_config.validate_strategy_config(config, _stock_config())

    assert any("threshold" in error and "ascending" in error for error in errors)


def test_reports_invalid_buy_sell_ratio_and_profit():
    config = _strategy_config()
    phase = config["raoeo"]["targets"]["SOXL"]["phase"][0]
    phase["buy"][0]["ratio"] = 2.5
    phase["sell"][0]["ratio"] = -0.1
    phase["sell"][1]["profit"] = 0.8

    errors = validate_config.validate_strategy_config(config, _stock_config())

    assert any("buy[0].ratio" in error for error in errors)
    assert any("sell[0].ratio" in error for error in errors)
    assert any("sell[1].profit" in error for error in errors)


def test_cli_returns_failure_for_invalid_config(tmp_path, capsys):
    config = _strategy_config()
    config["raoeo"]["targets"]["SOXL"]["seed"] = 0
    config_path = tmp_path / "strategy_config.json"
    stock_path = tmp_path / "stock_configuration.json"
    _write_json(config_path, config)
    _write_json(stock_path, _stock_config())

    exit_code = validate_config.main(
        [
            "--config",
            str(config_path),
            "--stocks",
            str(stock_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "SOXL.seed" in output


import asyncio
import sys
from pathlib import Path

import pandas as pd
from fastapi import BackgroundTasks

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from core import web_server


def test_cancel_order_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("WEB_ENABLE_ORDER_CANCEL", raising=False)

    def fail_if_called(order_id):
        raise AssertionError("_cancel_order_sync should not be called")

    monkeypatch.setattr(web_server, "_cancel_order_sync", fail_if_called)

    result = asyncio.run(web_server.cancel_order("12345"))

    assert result == {
        "success": False,
        "error": "Order cancel endpoint is disabled",
    }


def test_cancel_order_sync_matches_toss_order_id(monkeypatch):
    from broker import order_admin

    calls = {}

    def fake_fetch_open_orders():
        return (
            pd.DataFrame([
                {
                    "_market": "TOSS",
                    "orderId": "toss-order-1",
                    "symbol": "QQQM",
                }
            ]),
            0,
            0,
            1,
        )

    def fake_execute_manage_action(market, action_type, order_data, new_price):
        calls["market"] = market
        calls["action_type"] = action_type
        calls["order_id"] = order_data["orderId"]
        calls["new_price"] = new_price
        return pd.DataFrame([{"orderId": "toss-order-1"}]), None

    monkeypatch.setattr(order_admin, "fetch_open_orders", fake_fetch_open_orders)
    monkeypatch.setattr(order_admin, "execute_manage_action", fake_execute_manage_action)

    result = web_server._cancel_order_sync("toss-order-1")

    assert result == {"success": True, "message": "Cancel request submitted"}
    assert calls == {
        "market": "TOSS",
        "action_type": "2",
        "order_id": "toss-order-1",
        "new_price": None,
    }


def test_manual_report_trigger_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("WEB_ENABLE_MANUAL_REPORT_TRIGGERS", raising=False)
    background_tasks = BackgroundTasks()

    result = asyncio.run(web_server.trigger_portfolio_report(background_tasks))

    assert result == {
        "success": False,
        "error": "Manual report trigger endpoint is disabled",
    }
    assert background_tasks.tasks == []


import sys
import types
from pathlib import Path
import importlib.util

import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC_DIR))


def _load_main(monkeypatch):
    fake_kis = types.ModuleType("kis")
    fake_event_pipe = types.ModuleType("core.event_pipe")
    fake_event_pipe.create_pipe_server = lambda: False

    monkeypatch.setitem(sys.modules, "kis", fake_kis)
    monkeypatch.setitem(sys.modules, "core.event_pipe", fake_event_pipe)

    spec = importlib.util.spec_from_file_location("main_under_test", SRC_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, success, error=None):
        self.success = success
        self.error = error


def _install_fake_kis_thread(
    monkeypatch,
    main_module,
    rest_response,
    ws_response,
    ws_init_success=True,
):
    calls = []
    fake_kis_thread = types.ModuleType("broker.kis_worker")

    def start_kis_thread():
        calls.append("start_kis_thread")
        return True

    def request_kis_auth():
        calls.append("request_kis_auth")
        return "rest"

    def request_kis_ws_auth():
        calls.append("request_kis_ws_auth")
        return "ws"

    def wait_for_response(request_id, timeout=30.0):
        calls.append(f"wait_for_response:{request_id}")
        if request_id == "rest":
            return rest_response
        if request_id == "ws":
            return ws_response
        raise AssertionError(f"unexpected request id: {request_id}")

    def initialize_websocket_and_pipe():
        calls.append("initialize_websocket_and_pipe")
        return ws_init_success

    fake_kis_thread.start_kis_thread = start_kis_thread
    fake_kis_thread.is_kis_thread_running = lambda: False
    fake_kis_thread.request_kis_auth = request_kis_auth
    fake_kis_thread.request_kis_ws_auth = request_kis_ws_auth
    fake_kis_thread.wait_for_response = wait_for_response
    fake_kis_thread.initialize_websocket_and_pipe = initialize_websocket_and_pipe

    monkeypatch.setitem(sys.modules, "broker.kis_worker", fake_kis_thread)

    fake_broker = types.ModuleType("broker")
    fake_order_admin = types.ModuleType("broker.order_admin")

    def sync_open_orders():
        calls.append("sync_open_orders")

    fake_order_admin.sync_open_orders = sync_open_orders
    monkeypatch.setitem(sys.modules, "broker", fake_broker)
    monkeypatch.setitem(sys.modules, "broker.order_admin", fake_order_admin)

    monkeypatch.setattr(main_module.event_pipe, "create_pipe_server", lambda: False)
    return calls


def test_initialize_kis_fails_closed_when_rest_auth_fails(monkeypatch):
    main = _load_main(monkeypatch)
    calls = _install_fake_kis_thread(
        monkeypatch,
        main,
        rest_response=_Response(False, "REST failed"),
        ws_response=_Response(True),
    )

    system = main.TradingSystem()

    assert system.initialize_kis() is False
    assert "request_kis_ws_auth" not in calls
    assert "initialize_websocket_and_pipe" not in calls
    assert "sync_open_orders" not in calls


def test_initialize_kis_fails_closed_when_ws_auth_fails(monkeypatch):
    main = _load_main(monkeypatch)
    calls = _install_fake_kis_thread(
        monkeypatch,
        main,
        rest_response=_Response(True),
        ws_response=_Response(False, "WS failed"),
    )

    system = main.TradingSystem()

    assert system.initialize_kis() is False
    assert "initialize_websocket_and_pipe" not in calls
    assert "sync_open_orders" not in calls


def test_run_exits_before_scheduler_and_web_when_kis_init_fails(monkeypatch):
    main = _load_main(monkeypatch)
    calls = []
    system = main.TradingSystem()

    monkeypatch.setenv("ENV_MODE", "docker")
    monkeypatch.setattr(main.lock_manager, "acquire_lock", lambda _base_dir: True)
    monkeypatch.setattr(system, "setup_logging", lambda: calls.append("setup_logging"))
    monkeypatch.setattr(system, "initialize_telegram", lambda: calls.append("telegram"))
    monkeypatch.setattr(system, "initialize_kis", lambda: False)
    monkeypatch.setattr(system, "start_scheduler", lambda: calls.append("scheduler"))
    monkeypatch.setattr(system, "start_web_server", lambda: calls.append("web"))
    monkeypatch.setattr(system, "shutdown", lambda: calls.append("shutdown"))

    with pytest.raises(SystemExit) as exc_info:
        system.run()

    assert exc_info.value.code == 1
    assert calls == ["setup_logging", "telegram", "shutdown"]


def test_run_exits_before_scheduler_and_web_when_toss_init_fails(monkeypatch):
    main = _load_main(monkeypatch)
    calls = []
    system = main.TradingSystem()

    monkeypatch.setenv("ENV_MODE", "docker")
    monkeypatch.setattr(main.lock_manager, "acquire_lock", lambda _base_dir: True)
    monkeypatch.setattr(system, "setup_logging", lambda: calls.append("setup_logging"))
    monkeypatch.setattr(system, "initialize_telegram", lambda: calls.append("telegram"))
    monkeypatch.setattr(system, "initialize_kis", lambda: True)
    monkeypatch.setattr(system, "initialize_toss", lambda: False)
    monkeypatch.setattr(system, "start_scheduler", lambda: calls.append("scheduler"))
    monkeypatch.setattr(system, "start_web_server", lambda: calls.append("web"))
    monkeypatch.setattr(system, "shutdown", lambda: calls.append("shutdown"))

    with pytest.raises(SystemExit) as exc_info:
        system.run()

    assert exc_info.value.code == 1
    assert calls == ["setup_logging", "telegram", "shutdown"]
