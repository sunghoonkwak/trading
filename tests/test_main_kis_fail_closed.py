import sys
import types
from pathlib import Path
import importlib.util

import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))


def _load_main(monkeypatch):
    fake_kis = types.ModuleType("kis")
    fake_event_pipe = types.ModuleType("kis.event_pipe")
    fake_event_pipe.create_pipe_server = lambda: False
    fake_kis.event_pipe = fake_event_pipe

    monkeypatch.setitem(sys.modules, "kis", fake_kis)
    monkeypatch.setitem(sys.modules, "kis.event_pipe", fake_event_pipe)

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
    fake_kis_thread = types.ModuleType("kis.kis_thread")

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

    monkeypatch.setitem(sys.modules, "kis.kis_thread", fake_kis_thread)

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
