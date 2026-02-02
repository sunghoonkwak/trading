# -*- coding: utf-8 -*-
"""
Scheduler Main Service
Orchestrates all scheduled tasks by importing specific job modules.
"""
import logging
import time
import threading
import schedule

# Import jobs from sub-modules
from scheduler.scheduler_portfolio import run_daily_portfolio_report
from scheduler.scheduler_order import run_daily_order_report

def run_scheduler_loop():
    """Background thread loop."""
    while True:
        schedule.run_pending()
        time.sleep(600)


def start_scheduler():
    """Initialize and start the scheduler."""
    # Schedule Daily Jobs
    # 7:00 AM - Portfolio Summary
    schedule.every().day.at("07:00").do(run_daily_portfolio_report)

    # 9:00 PM - Order Checks (RAOEO / VA)
    schedule.every().day.at("21:00").do(run_daily_order_report)

    logging.info("[Scheduler] Scheduler started.")
    logging.info(" - 07:00 : Portfolio Report")
    logging.info(" - 21:00 : Order Report (RAOEO/VA)")

    t = threading.Thread(target=run_scheduler_loop, daemon=True)
    t.start()
