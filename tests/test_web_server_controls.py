import asyncio
import sys
from pathlib import Path

from fastapi import BackgroundTasks

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core import web_server


def test_env_flag_defaults_to_false(monkeypatch):
    monkeypatch.delenv("WEB_ENABLE_ORDER_CANCEL", raising=False)

    assert web_server._env_flag("WEB_ENABLE_ORDER_CANCEL") is False


def test_env_flag_accepts_true_values(monkeypatch):
    monkeypatch.setenv("WEB_ENABLE_ORDER_CANCEL", "true")

    assert web_server._env_flag("WEB_ENABLE_ORDER_CANCEL") is True


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


def test_cancel_order_calls_sync_path_when_enabled(monkeypatch):
    monkeypatch.setenv("WEB_ENABLE_ORDER_CANCEL", "true")
    called = {}

    def fake_cancel(order_id):
        called["order_id"] = order_id
        return {"success": True, "message": "cancelled"}

    monkeypatch.setattr(web_server, "_cancel_order_sync", fake_cancel)

    result = asyncio.run(web_server.cancel_order("12345"))

    assert called == {"order_id": "12345"}
    assert result == {"success": True, "message": "cancelled"}


def test_manual_report_trigger_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("WEB_ENABLE_MANUAL_REPORT_TRIGGERS", raising=False)
    background_tasks = BackgroundTasks()

    result = asyncio.run(web_server.trigger_portfolio_report(background_tasks))

    assert result == {
        "success": False,
        "error": "Manual report trigger endpoint is disabled",
    }
    assert background_tasks.tasks == []
