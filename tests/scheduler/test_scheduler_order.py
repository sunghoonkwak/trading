import sys
from pathlib import Path


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
