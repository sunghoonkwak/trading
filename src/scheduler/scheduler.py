# -*- coding: utf-8 -*-
"""
Scheduler Main Service
Orchestrates all scheduled tasks by importing specific job modules.
"""
import logging
import time
import threading
from datetime import datetime

import pytz
import schedule

# Import jobs from sub-modules
from scheduler.scheduler_portfolio import run_daily_portfolio_report
from scheduler.scheduler_order import run_daily_order_report, run_periodic_rebalancing

# Target times in US/Eastern (hour, minute)
ORDER_REPORT_ET = (7, 0)  # 07:00 ET

# Track current DST-adjusted KST schedule time
_current_order_kst = ""


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
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            logging.error(f"[Scheduler] Error in run_pending: {e}")
        time.sleep(60)


def start_scheduler():
    """Initialize and start the scheduler."""
    global _current_order_kst

    # Portfolio Report — KST fixed (Korean morning report)
    schedule.every().day.at("07:00").do(run_daily_portfolio_report)

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

    t = threading.Thread(target=run_scheduler_loop, daemon=True)
    t.start()
