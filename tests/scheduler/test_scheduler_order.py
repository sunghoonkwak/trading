import logging
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_daily_order_report_runs_strategy_suite_once(monkeypatch):
    from interfaces.scheduler import order_runner as scheduler_order

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
    scheduler_order.configure_notification_sender(notifications.append)

    scheduler_order.run_daily_order_report()

    assert calls == [True]
    assert notifications == [
        "⏰ <b>Daily Scheduler Execution</b>\n\nstrategy report"
    ]


def test_scheduler_strategy_suite_uses_the_application_facade(monkeypatch):
    from interfaces.scheduler import order_runner as scheduler_order

    class Service:
        def run_suite(self, *, execute):
            return ({"execute": execute}, {})

    scheduler_order.configure_strategy_run_service(Service())

    assert scheduler_order.run_strategy_suite(execute=True) == ({"execute": True}, {})


def test_scheduler_rebalancing_uses_application_facade_with_cache_key(monkeypatch):
    from interfaces.scheduler import order_runner as scheduler_order

    class Service:
        def run_rebalancing(self, *, execute, orderable_cache_key):
            return {"execute": execute, "cache_key": orderable_cache_key}

    scheduler_order.configure_strategy_run_service(Service())

    assert scheduler_order.run_rebalancing_strategy(
        execute=True,
        orderable_cache_key="2026-07-11",
    ) == {"execute": True, "cache_key": "2026-07-11"}


def test_periodic_rebalancing_is_quiet_when_disabled(monkeypatch, caplog):
    from interfaces.scheduler import order_runner as scheduler_order
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
    scheduler_order.configure_notification_sender(notifications.append)

    caplog.set_level(logging.INFO)
    scheduler_order._last_first_notify_date = ""

    with patch("datetime.datetime", FrozenDateTime):
        scheduler_order.run_periodic_rebalancing()

    assert calls == [(True, "2026-06-23")]
    assert notifications == []
    assert "Running periodic rebalancing" not in caplog.text
    assert "Rebalancing checked: No action needed." not in caplog.text
