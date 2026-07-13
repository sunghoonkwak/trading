import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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

        config_root = self._temporary_directory()
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

        config_root = self._temporary_directory()
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

    def _temporary_directory(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name)


def test_kis_rest_api_flag_defaults_to_enabled(monkeypatch):
    from core import trading_config

    monkeypatch.delenv("KIS_ENABLE_REST_API", raising=False)

    assert trading_config.is_kis_rest_api_enabled() is True


def test_kis_rest_api_flag_can_be_disabled(monkeypatch):
    from core import trading_config

    for value in ["0", "false", "no", "off"]:
        monkeypatch.setenv("KIS_ENABLE_REST_API", value)

        assert trading_config.is_kis_rest_api_enabled() is False


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
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import BackgroundTasks

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from interfaces.web import server as web_server


@pytest.fixture(autouse=True)
def web_dependencies(monkeypatch):
    """Configure the web adapter with local fakes, not legacy imports."""
    order_admin = SimpleNamespace(
        sync_open_orders=lambda: None,
        fetch_open_orders=lambda: (pd.DataFrame(), 0, 0, 0),
        execute_manage_action=lambda *_args: (pd.DataFrame(), None),
    )
    runtime_control = SimpleNamespace(is_runtime_running=lambda: True)
    monkeypatch.setattr(web_server, "order_admin", order_admin, raising=False)
    monkeypatch.setattr(web_server, "runtime_control", runtime_control, raising=False)
    application = web_server.create_web_app(
        web_server.WebDependencies(
            runtime_is_running=lambda: web_server.runtime_control.is_runtime_running(),
            set_broadcast_callback=lambda _callback: None,
            load_memos=lambda: {},
            save_memos=lambda _memos: True,
            portfolio_reader=SimpleNamespace(get_portfolio_data=lambda: {}),
            sync_open_orders=lambda: web_server.order_admin.sync_open_orders(),
            fetch_open_orders=lambda: web_server.order_admin.fetch_open_orders(),
            execute_manage_action=lambda *args: web_server.order_admin.execute_manage_action(*args),
            run_portfolio_report=lambda _reader: None,
            run_order_report=lambda: None,
            env_flag=lambda name, default=False: os.environ.get(name, "").lower()
            in {"1", "true", "yes", "on"} if name in os.environ else default,
        )
    )
    with web_server.bind_web_runtime(application):
        yield


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


def test_web_factory_keeps_independent_compositions():
    def make_app(running):
        return web_server.create_web_app(
            web_server.WebDependencies(
                runtime_is_running=lambda: running,
                set_broadcast_callback=lambda _callback: None,
                load_memos=lambda: {},
                save_memos=lambda _memos: True,
                portfolio_reader=SimpleNamespace(get_portfolio_data=lambda: {}),
                sync_open_orders=lambda: None,
                fetch_open_orders=lambda: (pd.DataFrame(), 0, 0, 0),
                execute_manage_action=lambda *_args: (pd.DataFrame(), None),
                run_portfolio_report=lambda _reader: None,
                run_order_report=lambda: None,
                env_flag=lambda _name, default=False: default,
            )
        )

    running_app = make_app(True)
    stopped_app = make_app(False)

    assert running_app is not stopped_app
    assert stopped_app.state.web_runtime is not running_app.state.web_runtime
    assert running_app.state.web_runtime.dependencies.runtime_is_running() is True
    assert stopped_app.state.web_runtime.dependencies.runtime_is_running() is False


def test_cancel_order_sync_matches_toss_order_id(monkeypatch):
    order_admin = web_server.order_admin

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


def test_web_order_sync_is_blocked_when_runtime_is_off(monkeypatch):
    runtime_control = web_server.runtime_control

    monkeypatch.setattr(runtime_control, "is_runtime_running", lambda: False)

    fake_order_admin = types.ModuleType("broker.order_admin")

    def fail_if_called():
        raise AssertionError("open orders must not sync while runtime is off")

    fake_order_admin.sync_open_orders = fail_if_called
    monkeypatch.setitem(sys.modules, "broker.order_admin", fake_order_admin)

    result = asyncio.run(web_server._sync_orders_for_client())

    assert result == {
        "success": False,
        "error": "Trading runtime is OFF",
    }


def test_web_cancel_order_is_blocked_when_runtime_is_off(monkeypatch):
    runtime_control = web_server.runtime_control

    monkeypatch.setenv("WEB_ENABLE_ORDER_CANCEL", "true")
    monkeypatch.setattr(runtime_control, "is_runtime_running", lambda: False)

    calls = []

    def fake_cancel(order_id):
        calls.append(order_id)
        return {"success": True}

    monkeypatch.setattr(web_server, "_cancel_order_sync", fake_cancel)

    result = asyncio.run(web_server.cancel_order("12345"))

    assert result == {
        "success": False,
        "error": "Trading runtime is OFF",
    }
    assert calls == []


def test_web_manual_triggers_are_blocked_when_runtime_is_off(monkeypatch):
    runtime_control = web_server.runtime_control

    monkeypatch.setenv("WEB_ENABLE_MANUAL_REPORT_TRIGGERS", "true")
    monkeypatch.setattr(runtime_control, "is_runtime_running", lambda: False)
    background_tasks = BackgroundTasks()

    portfolio_result = asyncio.run(web_server.trigger_portfolio_report(background_tasks))
    order_result = asyncio.run(web_server.trigger_order_report(background_tasks))

    assert portfolio_result == {
        "success": False,
        "error": "Trading runtime is OFF",
    }
    assert order_result == {
        "success": False,
        "error": "Trading runtime is OFF",
    }
    assert background_tasks.tasks == []


def test_web_holdings_lookup_is_blocked_when_runtime_is_off(monkeypatch):
    runtime_control = web_server.runtime_control

    monkeypatch.setattr(runtime_control, "is_runtime_running", lambda: False)

    fake_data_service = types.ModuleType("data.data_service")

    def fail_if_called():
        raise AssertionError("portfolio data must not load while runtime is off")

    fake_data_service.get_portfolio_data = fail_if_called
    monkeypatch.setitem(sys.modules, "data.data_service", fake_data_service)

    result = asyncio.run(web_server.get_holdings_data("SOXL"))

    assert result == {
        "success": False,
        "error": "Trading runtime is OFF",
    }


import importlib.util
import sys
import types
from pathlib import Path

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
    fake_kis_event_handler = types.ModuleType("broker.kis_event_handler")
    fake_order_admin = types.ModuleType("broker.order_admin")

    def sync_open_orders():
        calls.append("sync_open_orders")

    fake_order_admin.sync_open_orders = sync_open_orders
    fake_kis_event_handler.on_result = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "broker", fake_broker)
    monkeypatch.setitem(sys.modules, "broker.kis_event_handler", fake_kis_event_handler)
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


def test_initialize_kis_skips_rest_auth_when_rest_api_disabled(monkeypatch):
    monkeypatch.setenv("KIS_ENABLE_REST_API", "false")
    main = _load_main(monkeypatch)
    calls = _install_fake_kis_thread(
        monkeypatch,
        main,
        rest_response=_Response(False, "REST should be skipped"),
        ws_response=_Response(True),
    )

    system = main.TradingSystem()

    assert system.initialize_kis() is True
    assert "request_kis_auth" not in calls
    assert "wait_for_response:rest" not in calls
    assert "request_kis_ws_auth" in calls
    assert "initialize_websocket_and_pipe" in calls
    assert "sync_open_orders" in calls


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


def test_run_starts_control_plane_and_waits_for_runtime_command(monkeypatch):
    main = _load_main(monkeypatch)
    calls = []
    system = main.TradingSystem()

    monkeypatch.setenv("ENV_MODE", "docker")
    monkeypatch.setattr(main.lock_manager, "acquire_lock", lambda _base_dir: True)
    monkeypatch.setattr(system, "setup_logging", lambda: calls.append("setup_logging"))
    monkeypatch.setattr(system, "initialize_telegram", lambda: calls.append("telegram") or True)
    monkeypatch.setattr(system, "initialize_gsheet_cache", lambda: calls.append("gsheet"))
    monkeypatch.setattr(system, "initialize_kis", lambda: calls.append("kis") or True)
    monkeypatch.setattr(system, "initialize_toss", lambda: calls.append("toss") or True)
    monkeypatch.setattr(system, "start_scheduler", lambda: calls.append("scheduler"))
    monkeypatch.setattr(system, "start_web_server", lambda: calls.append("web"))
    monkeypatch.setattr(system, "shutdown", lambda: calls.append("shutdown"))
    sleeps = []

    def fake_sleep(_seconds):
        sleeps.append(_seconds)
        system.shutdown_event.set()

    monkeypatch.setattr(main.time, "sleep", fake_sleep)

    system.run()

    assert calls == ["setup_logging", "telegram", "web", "shutdown"]
    assert sleeps == [1]


def test_runtime_on_starts_trading_dependencies(monkeypatch):
    main = _load_main(monkeypatch)
    calls = []
    system = main.TradingSystem()

    monkeypatch.setattr(system, "initialize_gsheet_cache", lambda: calls.append("gsheet"))
    monkeypatch.setattr(system, "initialize_kis", lambda: calls.append("kis") or True)
    monkeypatch.setattr(system, "initialize_toss", lambda: calls.append("toss") or True)
    monkeypatch.setattr(system, "start_scheduler", lambda: calls.append("scheduler"))

    result = system.start_trading_runtime()

    assert result.success is True
    assert result.already_in_state is False
    assert system.is_trading_runtime_running() is True
    assert calls == ["gsheet", "kis", "toss", "scheduler"]


def test_runtime_on_failure_keeps_process_alive_and_off(monkeypatch):
    main = _load_main(monkeypatch)
    calls = []
    notifications = []
    system = main.TradingSystem()

    monkeypatch.setattr(system, "initialize_gsheet_cache", lambda: calls.append("gsheet"))
    monkeypatch.setattr(system, "initialize_kis", lambda: calls.append("kis") or False)
    monkeypatch.setattr(system, "initialize_toss", lambda: calls.append("toss") or True)
    monkeypatch.setattr(system, "start_scheduler", lambda: calls.append("scheduler"))
    monkeypatch.setattr(system, "start_web_server", lambda: calls.append("web"))
    monkeypatch.setattr(system, "_notify_startup_failure", lambda component: notifications.append(component))

    result = system.start_trading_runtime()

    assert result.success is False
    assert result.component == "KIS"
    assert system.is_trading_runtime_running() is False
    assert calls == ["gsheet", "kis"]
    assert notifications == ["KIS"]


def test_runtime_off_stops_scheduler_and_kis_but_keeps_telegram(monkeypatch):
    main = _load_main(monkeypatch)
    calls = []
    system = main.TradingSystem()
    system._runtime_running = True

    system._scheduler_runner = SimpleNamespace(stop=lambda: calls.append("stop_scheduler"))
    fake_kis_worker = types.ModuleType("broker.kis_worker")
    fake_kis_worker.stop_kis_thread = lambda: calls.append("stop_kis_thread")
    monkeypatch.setitem(sys.modules, "broker.kis_worker", fake_kis_worker)

    result = system.stop_trading_runtime()

    assert result.success is True
    assert result.already_in_state is False
    assert system.is_trading_runtime_running() is False
    assert calls == ["stop_scheduler", "stop_kis_thread"]


def test_runtime_off_is_idempotent(monkeypatch):
    main = _load_main(monkeypatch)
    system = main.TradingSystem()

    result = system.stop_trading_runtime()

    assert result.success is True
    assert result.already_in_state is True
    assert system.is_trading_runtime_running() is False


def test_runtime_off_waits_for_in_progress_runtime_on(monkeypatch):
    main = _load_main(monkeypatch)
    system = main.TradingSystem()
    startup_entered = threading.Event()
    allow_startup = threading.Event()
    stop_called = threading.Event()
    results = {}

    def block_gsheet_initialization():
        startup_entered.set()
        assert allow_startup.wait(timeout=1)

    monkeypatch.setattr(system, "initialize_gsheet_cache", block_gsheet_initialization)
    monkeypatch.setattr(system, "initialize_kis", lambda: True)
    monkeypatch.setattr(system, "initialize_toss", lambda: True)
    monkeypatch.setattr(system, "start_scheduler", lambda: None)
    monkeypatch.setattr(main.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        system,
        "_stop_runtime_dependencies",
        lambda: stop_called.set(),
    )

    start_thread = threading.Thread(
        target=lambda: results.setdefault("on", system.start_trading_runtime())
    )
    stop_thread = threading.Thread(
        target=lambda: results.setdefault("off", system.stop_trading_runtime())
    )
    start_thread.start()
    assert startup_entered.wait(timeout=1)
    stop_thread.start()

    assert not stop_called.wait(timeout=0.05)
    allow_startup.set()
    start_thread.join(timeout=1)
    stop_thread.join(timeout=1)

    assert not start_thread.is_alive()
    assert not stop_thread.is_alive()
    assert results["on"].success is True
    assert results["off"].success is True
    assert stop_called.is_set()
    assert system.is_trading_runtime_running() is False


def test_previous_startup_failures_are_deferred_to_runtime_on(monkeypatch):
    main = _load_main(monkeypatch)
    calls = []
    system = main.TradingSystem()

    monkeypatch.setenv("ENV_MODE", "docker")
    monkeypatch.setattr(main.lock_manager, "acquire_lock", lambda _base_dir: True)
    monkeypatch.setattr(system, "setup_logging", lambda: calls.append("setup_logging"))
    monkeypatch.setattr(system, "initialize_telegram", lambda: calls.append("telegram") or True)
    monkeypatch.setattr(system, "initialize_gsheet_cache", lambda: calls.append("gsheet"))
    monkeypatch.setattr(system, "initialize_kis", lambda: calls.append("kis") or False)
    monkeypatch.setattr(system, "start_web_server", lambda: calls.append("web"))
    monkeypatch.setattr(system, "shutdown", lambda: calls.append("shutdown"))

    def fake_sleep(_seconds):
        system.shutdown_event.set()

    monkeypatch.setattr(main.time, "sleep", fake_sleep)

    system.run()

    assert calls == ["setup_logging", "telegram", "web", "shutdown"]


def test_run_exits_before_dependencies_when_telegram_init_fails(monkeypatch):
    main = _load_main(monkeypatch)
    calls = []
    system = main.TradingSystem()

    monkeypatch.setenv("ENV_MODE", "docker")
    monkeypatch.setattr(main.lock_manager, "acquire_lock", lambda _base_dir: True)
    monkeypatch.setattr(system, "setup_logging", lambda: calls.append("setup_logging"))
    monkeypatch.setattr(system, "initialize_telegram", lambda: calls.append("telegram") or False)
    monkeypatch.setattr(system, "initialize_gsheet_cache", lambda: calls.append("gsheet"))
    monkeypatch.setattr(system, "initialize_kis", lambda: calls.append("kis") or True)
    monkeypatch.setattr(system, "initialize_toss", lambda: calls.append("toss") or True)
    monkeypatch.setattr(system, "start_scheduler", lambda: calls.append("scheduler"))
    monkeypatch.setattr(system, "start_web_server", lambda: calls.append("web"))
    monkeypatch.setattr(system, "shutdown", lambda: calls.append("shutdown"))

    with pytest.raises(SystemExit) as exc_info:
        system.run()

    assert exc_info.value.code == 1
    assert calls == ["setup_logging", "telegram", "shutdown"]


def test_notify_startup_failure_sends_telegram_alert(monkeypatch):
    main = _load_main(monkeypatch)
    messages = []
    fake_telegram_utils = types.ModuleType("interfaces.telegram.utils")
    fake_telegram_utils.send_notification = lambda message: messages.append(message)
    monkeypatch.setitem(sys.modules, "interfaces.telegram.utils", fake_telegram_utils)

    main.TradingSystem()._notify_startup_failure("Toss")

    assert len(messages) == 1
    assert "Startup failure" in messages[0]
    assert "Toss" in messages[0]
