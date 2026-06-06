import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scheduler import scheduler_order
from strategy.base import StrategyStatus


def test_first_periodic_rebalancing_notifies_when_already_done(monkeypatch):
    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return cls()

        def strftime(self, fmt):
            values = {
                "%Y-%m-%d": "2026-06-05",
                "%H:%M": "09:40",
            }
            return values[fmt]

    monkeypatch.setitem(
        sys.modules,
        "datetime",
        SimpleNamespace(datetime=FixedDateTime),
    )
    monkeypatch.setattr(scheduler_order, "_last_first_notify_date", "")
    monkeypatch.setattr(
        scheduler_order,
        "run_rebalancing_strategy",
        lambda execute, orderable_cache_key: {
            "status": StrategyStatus.ALREADY_DONE,
            "orders": [],
            "info": {},
        },
    )

    notifications = []
    monkeypatch.setattr(
        scheduler_order,
        "send_notification",
        lambda text: notifications.append(text),
    )

    import strategy.report_formatter as report_formatter

    monkeypatch.setattr(
        report_formatter,
        "format_rebalancing_report",
        lambda report: "already done",
    )

    scheduler_order.run_periodic_rebalancing()

    assert notifications == [
        "🚀 <b>First Rebalancing Check</b>\n\nalready done"
    ]
    assert scheduler_order._last_first_notify_date == "2026-06-05"
