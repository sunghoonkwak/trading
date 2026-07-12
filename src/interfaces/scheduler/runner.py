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
from interfaces.scheduler.order_runner import (
    SchedulerOrderRunner,
    run_daily_order_report,
    run_periodic_rebalancing,
)
from interfaces.scheduler.portfolio_runner import run_daily_portfolio_report

# Target times in US/Eastern (hour, minute)
ORDER_REPORT_ET = (7, 0)  # 07:00 ET

# Track current DST-adjusted KST schedule time
_current_order_kst = ""
_scheduler_thread = None
_stop_event = threading.Event()
_portfolio_reader: PortfolioReader | None = None


class SchedulerRunner:
    """Factory-owned scheduler lifecycle used by the production composition root."""

    def __init__(
        self,
        *,
        portfolio_reader: PortfolioReader,
        order_runner: SchedulerOrderRunner,
    ) -> None:
        self._portfolio_reader = portfolio_reader
        self._order_runner = order_runner
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
        schedule.every().day.at("07:00").do(
            run_daily_portfolio_report,
            self._portfolio_reader,
        )
        self._current_order_kst = _et_to_kst(*ORDER_REPORT_ET)
        schedule.every().day.at(self._current_order_kst).do(
            self._order_runner.run_daily_order_report
        ).tag("order_report")
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


def set_portfolio_reader(reader: PortfolioReader) -> None:
    """Inject the portfolio use case required by the scheduled report."""
    global _portfolio_reader
    _portfolio_reader = reader


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


def _reschedule_if_dst_changed():
    """Check if DST status changed and reschedule order report if needed."""
    global _current_order_kst
    new_kst = _et_to_kst(*ORDER_REPORT_ET)
    if new_kst != _current_order_kst:
        logging.info(
            f"[Scheduler] DST change detected: {_current_order_kst} -> {new_kst} KST"
        )
        schedule.clear('order_report')
        schedule.every().day.at(new_kst).do(
            run_daily_order_report
        ).tag('order_report')
        _current_order_kst = new_kst
        logging.info(f"[Scheduler] Order report rescheduled to {new_kst} KST")


def run_scheduler_loop():
    """Background thread loop."""
    while not _stop_event.is_set():
        try:
            schedule.run_pending()
        except Exception as e:
            logging.error(f"[Scheduler] Error in run_pending: {e}")
        _stop_event.wait(60)


def start_scheduler():
    """Initialize and start the scheduler."""
    global _current_order_kst, _scheduler_thread

    if _scheduler_thread and _scheduler_thread.is_alive():
        logging.info("[Scheduler] Scheduler already running.")
        return

    _stop_event.clear()
    schedule.clear()

    # Portfolio Report — KST fixed (Korean morning report)
    if _portfolio_reader is None:
        raise RuntimeError("PortfolioReader must be configured before starting the scheduler.")
    schedule.every().day.at("07:00").do(run_daily_portfolio_report, _portfolio_reader)

    # Order Report (RAOEO/VA) — ET-based dynamic scheduling
    _current_order_kst = _et_to_kst(*ORDER_REPORT_ET)
    schedule.every().day.at(_current_order_kst).do(
        run_daily_order_report
    ).tag('order_report')

    # Periodic Rebalancing (Every 5 mins)
    # The time window check (09:40-15:40 ET) is inside the function
    schedule.every(5).minutes.do(run_periodic_rebalancing)

    # Daily DST check (00:05 KST — catches any overnight DST transition)
    schedule.every().day.at("00:05").do(_reschedule_if_dst_changed)

    et_h, et_m = ORDER_REPORT_ET
    logging.info("[Scheduler] Scheduler started.")
    logging.info(" - 07:00 KST : Portfolio Report")
    logging.info(
        f" - {_current_order_kst} KST : Order Report "
        f"(ET {et_h:02d}:{et_m:02d})"
    )
    logging.info(" - Every 5m : Periodic Rebalancing (09:40-15:40 ET)")

    _scheduler_thread = threading.Thread(
        target=run_scheduler_loop,
        daemon=True,
        name="SchedulerThread",
    )
    _scheduler_thread.start()


def stop_scheduler():
    """Stop scheduler loop and clear registered jobs."""
    global _scheduler_thread
    _stop_event.set()
    schedule.clear()
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=5.0)
    _scheduler_thread = None
    logging.info("[Scheduler] Scheduler stopped.")
