# -*- coding: utf-8 -*-
"""
Scheduler Order Service (Refactored)

Executes daily strategy routines automatically and sends reports to Telegram.
Reuses the same execution and reporting logic as the Telegram bot.
"""
import logging
from telegram_bot.telegram_utils import send_notification
from strategy.execution_service import run_raoeo_strategy, run_va_strategy, run_rebalancing_strategy
from strategy.report_formatter import format_strategy_report

def run_daily_order_report():
    """
    Execute daily order update routine (typically scheduled for evening).
    Calculates and Executes RAOEO and VA strategies, then sends a unified report.
    """
    logging.info("[Scheduler] Starting daily order report & execution job.")

    try:
        # Run RAOEO (Execute Mode)
        raoeo_res = run_raoeo_strategy(execute=True)

        # Run Value Averaging (Execute Mode)
        va_res = run_va_strategy(execute=True)

        # Format Unified Report
        report_text = format_strategy_report(raoeo_res, va_res)

        # Send Notification
        full_message = f"⏰ <b>Daily Scheduler Execution</b>\n\n{report_text}"
        send_notification(full_message)

        logging.info("[Scheduler] Daily execution completed and report sent.")

    except Exception as e:
        logging.error(f"[Scheduler] Daily Order Job failed: {e}", exc_info=True)
        send_notification(f"⚠️ Scheduler Order Error: {e}")

# Module-level flag: US/Eastern date of last first-notification
_last_first_notify_date: str = ""


def run_periodic_rebalancing():
    """
    Execute rebalancing strategy periodically during US market hours.
    Notification rules:
      1. First scheduled call of the US trading day -> ALWAYS notify
      2. Subsequent calls -> only notify if actual rebalancing orders exist
    """
    global _last_first_notify_date
    from datetime import datetime
    import pytz

    tz = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz)
    us_date = now_et.strftime("%Y-%m-%d")
    cur_time = now_et.strftime("%H:%M")

    # Time window: 09:40 ~ 15:40 US/Eastern
    if not ("09:40" <= cur_time <= "15:40"):
        return

    logging.info(f"[Scheduler] Running periodic rebalancing at {cur_time} ET ({us_date})")

    # First scheduled call of this US trading day?
    is_first_call = (us_date != _last_first_notify_date)

    try:
        reb_res = run_rebalancing_strategy(execute=True)

        # Notify if:
        # 1. First call of the day -> ALWAYS (regardless of holiday)
        # 2. Actual rebalancing orders exist or error occurred
        should_notify = is_first_call or reb_res.get('orders') or reb_res.get('error')

        if should_notify:
            from strategy.report_formatter import format_rebalancing_report
            header = "🚀 <b>First Rebalancing Check</b>" if is_first_call else "🔄 <b>Periodic Rebalancing</b>"
            report_text = format_rebalancing_report(reb_res)
            send_notification(f"{header}\n\n{report_text}")
            logging.info(f"[Scheduler] Rebalancing notification sent (FirstCall: {is_first_call})")
        else:
            logging.info(f"[Scheduler] Rebalancing checked: No action needed.")

        # Mark this date as notified (whether we sent or not, the day is checked)
        _last_first_notify_date = us_date

    except Exception as e:
        logging.error(f"[Scheduler] Periodic Rebalancing failed: {e}", exc_info=True)
        send_notification(f"⚠️ Periodic Rebalancing Error: {e}")
        # Still mark date so we don't retry first-call notification on error
        _last_first_notify_date = us_date
