import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

import logging


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_daily_order_report_runs_strategy_suite_once(monkeypatch):
    from scheduler import scheduler_order

    calls = []
    raoeo_report = {"status": "skipped", "error": None}
    va_report = {"status": "skipped", "error": None}

    monkeypatch.setattr(
        scheduler_order,
        "run_strategy_suite",
        lambda execute=False: calls.append(execute) or (raoeo_report, va_report),
    )
    monkeypatch.setattr(
        scheduler_order,
        "format_strategy_report",
        lambda raoeo, va: "strategy report",
    )

    notifications = []
    monkeypatch.setattr(
        scheduler_order,
        "send_notification",
        lambda message: notifications.append(message),
    )

    scheduler_order.run_daily_order_report()

    assert calls == [True]
    assert notifications == [
        "⏰ <b>Daily Scheduler Execution</b>\n\nstrategy report"
    ]


def test_periodic_rebalancing_is_quiet_when_disabled(monkeypatch, caplog):
    from scheduler import scheduler_order
    from strategy.base import StrategyStatus

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 6, 23, 10, 0, tzinfo=tz)

    calls = []
    monkeypatch.setattr(
        scheduler_order,
        "run_rebalancing_strategy",
        lambda execute=False, orderable_cache_key="": calls.append(
            (execute, orderable_cache_key)
        )
        or {"status": StrategyStatus.DISABLED},
    )

    notifications = []
    monkeypatch.setattr(
        scheduler_order,
        "send_notification",
        lambda message: notifications.append(message),
    )

    caplog.set_level(logging.INFO)
    scheduler_order._last_first_notify_date = ""

    with patch("datetime.datetime", FrozenDateTime):
        scheduler_order.run_periodic_rebalancing()

    assert calls == [(True, "2026-06-23")]
    assert notifications == []
    assert "Running periodic rebalancing" not in caplog.text
    assert "Rebalancing checked: No action needed." not in caplog.text
