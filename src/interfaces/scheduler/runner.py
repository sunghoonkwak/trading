# -*- coding: utf-8 -*-
"""
Scheduler Interface Runner
Orchestrates all scheduled tasks by importing specific job modules.
"""
import logging
import threading
from datetime import datetime

import pytz
import schedule

from application.ports import PortfolioReader
from interfaces.scheduler.order_runner import SchedulerOrderRunner
from interfaces.scheduler.portfolio_runner import SchedulerPortfolioRunner

# Target times in US/Eastern (hour, minute)
ORDER_REPORT_ET = (7, 0)  # 07:00 ET

class SchedulerRunner:
    """Factory-owned scheduler lifecycle used by the production composition root."""

    def __init__(
        self,
        *,
        portfolio_reader: PortfolioReader,
        order_runner: SchedulerOrderRunner,
        portfolio_runner: SchedulerPortfolioRunner,
    ) -> None:
        self._portfolio_reader = portfolio_reader
        self._order_runner = order_runner
        self._portfolio_runner = portfolio_runner
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._current_order_kst = ""

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                schedule.run_pending()
            except Exception as exc:
                logging.error("[Scheduler] Error in run_pending: %s", exc)
            self._stop_event.wait(60)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        schedule.clear()
        self._current_order_kst = ""
        schedule.every().day.at("07:00").do(
            self._portfolio_runner.run_daily_portfolio_report,
            self._portfolio_reader,
        )
        self._refresh_order_report_schedule()
        schedule.every().day.at("00:05").do(
            self._refresh_order_report_schedule
        ).tag("order_report_reschedule")
        schedule.every(5).minutes.do(self._order_runner.run_periodic_rebalancing)
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="SchedulerThread",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        schedule.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None

    def run_daily_order_report(self) -> None:
        """Run the injected order job for an authorized manual trigger."""
        self._order_runner.run_daily_order_report()

    def _refresh_order_report_schedule(self) -> None:
        """Re-register the order report when the ET-to-KST offset changes."""
        next_order_kst = _et_to_kst(*ORDER_REPORT_ET)
        if next_order_kst == self._current_order_kst:
            return

        schedule.clear("order_report")
        self._current_order_kst = next_order_kst
        schedule.every().day.at(next_order_kst).do(
            self._order_runner.run_daily_order_report
        ).tag("order_report")


def _et_to_kst(hour: int, minute: int = 0) -> str:
    """Convert US/Eastern time to Asia/Seoul time string for today."""
    tz_et = pytz.timezone('US/Eastern')
    tz_kst = pytz.timezone('Asia/Seoul')
    now_et = datetime.now(tz_et)
    # Create naive datetime for target time, then localize to ET
    naive_target = now_et.replace(
        hour=hour, minute=minute, second=0, microsecond=0, tzinfo=None
    )
    target_et = tz_et.localize(naive_target)
    target_kst = target_et.astimezone(tz_kst)
    return target_kst.strftime("%H:%M")
