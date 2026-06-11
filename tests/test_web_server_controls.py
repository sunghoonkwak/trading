import asyncio
import sys
from pathlib import Path

import pandas as pd
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

    async def run_cancel_inline():
        loop = asyncio.get_running_loop()

        def run_sync(executor, func, *args):
            future = loop.create_future()
            future.set_result(func(*args))
            return future

        monkeypatch.setattr(loop, "run_in_executor", run_sync)
        return await web_server.cancel_order("12345")

    result = asyncio.run(run_cancel_inline())

    assert called == {"order_id": "12345"}
    assert result == {"success": True, "message": "cancelled"}


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
