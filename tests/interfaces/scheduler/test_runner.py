import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))


class _FakeJob:
    def __init__(self, calls):
        self._calls = calls
        self.day = self

    def at(self, time):
        self._calls.append(("at", time))
        return self

    def do(self, callback, *args):
        self._calls.append(("do", callback, args))
        return self

    def tag(self, *tags):
        self._calls.append(("tag", tags))
        return self


class _FakeSchedule:
    def __init__(self):
        self.calls = []

    def clear(self, *tags):
        self.calls.append(("clear", tags))

    def every(self):
        return _FakeJob(self.calls)


def test_scheduler_refreshes_order_time_after_dst_change(monkeypatch):
    from interfaces.scheduler import runner

    fake_schedule = _FakeSchedule()
    times = iter(["20:00", "19:00"])
    scheduler = runner.SchedulerRunner(
        portfolio_reader=lambda: {},
        order_runner=type("OrderRunner", (), {"run_daily_order_report": lambda self: None})(),
        portfolio_runner=type("PortfolioRunner", (), {})(),
    )

    monkeypatch.setattr(runner, "schedule", fake_schedule)
    monkeypatch.setattr(runner, "_et_to_kst", lambda *_args: next(times))

    scheduler._refresh_order_report_schedule()
    scheduler._refresh_order_report_schedule()

    assert fake_schedule.calls == [
        ("clear", ("order_report",)),
        ("at", "20:00"),
        ("do", scheduler._order_runner.run_daily_order_report, ()),
        ("tag", ("order_report",)),
        ("clear", ("order_report",)),
        ("at", "19:00"),
        ("do", scheduler._order_runner.run_daily_order_report, ()),
        ("tag", ("order_report",)),
    ]
