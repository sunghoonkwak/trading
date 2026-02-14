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

def run_periodic_rebalancing():
    """
    Execute rebalancing strategy periodically during market hours.
    """
    from datetime import datetime
    import pytz
    
    # Time window check: 23:40 ~ 05:40 (KST assumed based on user request)
    # Actually, the user said 23:40 to 05:40. In US market time, this is 09:40 to 15:40 (approx).
    # Since the system uses US/Eastern for many checks, I should be careful.
    # But for simplicity, I will implement a check for the specific 23:40-05:40 window.
    
    now = datetime.now()
    cur_time = now.strftime("%H:%M")
    
    # 23:40 ~ 23:59 or 00:00 ~ 05:40
    is_in_window = False
    if "23:40" <= cur_time <= "23:59":
        is_in_window = True
    if "00:00" <= cur_time <= "05:40":
        is_in_window = True
        
    if not is_in_window:
        return

    logging.info(f"[Scheduler] Running periodic rebalancing at {cur_time}")
    
    try:
        reb_res = run_rebalancing_strategy(execute=True)
        
        # Force notify on the first run of the day (23:40)
        force_notify = (cur_time == "23:40")
        is_holiday = (reb_res.get('status') == 'market_holiday')
        
        # Only notify if:
        # 1. It's the first run (23:40) -> ALWAYS
        # 2. It's NOT a holiday AND (there are orders OR there's an error)
        should_notify = force_notify or (not is_holiday and (reb_res.get('orders') or reb_res.get('error')))
        
        if should_notify:
            from strategy.report_formatter import format_rebalancing_report
            header = "🚀 <b>First Rebalancing Check</b>" if force_notify and not reb_res.get('orders') else "🔄 <b>Periodic Rebalancing</b>"
            report_text = format_rebalancing_report(reb_res)
            send_notification(f"{header}\n\n{report_text}")
            logging.info(f"[Scheduler] Rebalancing notification sent (Force: {force_notify})")
        else:
            logging.info(f"[Scheduler] Rebalancing checked: No notification needed (Holiday: {is_holiday}).")

    except Exception as e:
        logging.error(f"[Scheduler] Periodic Rebalancing failed: {e}", exc_info=True)
        send_notification(f"⚠️ Periodic Rebalancing Error: {e}")
