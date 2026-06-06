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

        raoeo_err = raoeo_res.get("error")
        va_err = va_res.get("error")
        if raoeo_err == "API Timeout" or va_err == "API Timeout":
            send_notification(f"⚠️ [네트워크 타임아웃] KIS API 무응답 (Daily Report)\nRAOEO: {raoeo_err}, VA: {va_err}")

        # Format Unified Report
        report_text = format_strategy_report(raoeo_res, va_res)

        # Send Notification
        full_message = f"⏰ <b>Daily Scheduler Execution</b>\n\n{report_text}"
        send_notification(full_message)

        logging.info("[Scheduler] Daily execution completed and report sent.")

    except Exception as e:
        if "Timeout" in str(e):
            alert_msg = f"⚠️ [네트워크 타임아웃] KIS API 무응답 (Daily Order): {e}"
        else:
            alert_msg = f"⚠️ Scheduler Order Error: {e}"
        logging.error(f"[Scheduler] Daily Order Job failed: {e}", exc_info=True)
        send_notification(alert_msg)

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
        reb_res = run_rebalancing_strategy(
            execute=True,
            orderable_cache_key=us_date,
        )

        from strategy.base import StrategyStatus

        # Notify on the first market-window check, or later only when the
        # strategy actually acted or surfaced an error.

        status = reb_res.get('status')

        if status == StrategyStatus.ALREADY_DONE:
            should_notify = False
        elif is_first_call:
            should_notify = True
        else:
            # For subsequent calls, only notify if action was taken
            should_notify = status in [StrategyStatus.EXECUTED, StrategyStatus.PARTIAL, StrategyStatus.ERROR]


        if should_notify:
            if status == StrategyStatus.ERROR and reb_res.get("error") == "API Timeout":
                send_notification(f"⚠️ [네트워크 타임아웃] KIS API 무응답 (Periodic Rebalancing)")
            else:
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
        if "Timeout" in str(e):
            alert_msg = f"⚠️ [네트워크 타임아웃] KIS API 무응답 (Rebalancing): {e}"
        else:
            alert_msg = f"⚠️ Periodic Rebalancing Error: {e}"
        logging.error(f"[Scheduler] Periodic Rebalancing failed: {e}", exc_info=True)
        send_notification(alert_msg)
        # Still mark date so we don't retry first-call notification on error
        _last_first_notify_date = us_date
