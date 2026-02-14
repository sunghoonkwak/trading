# -*- coding: utf-8 -*-
"""
Scheduler Order Service (Refactored)

Executes daily strategy routines automatically and sends reports to Telegram.
Reuses the same execution and reporting logic as the Telegram bot.
"""
import logging
from telegram_bot.telegram_utils import send_notification
from strategy.execution_service import run_raoeo_strategy, run_va_strategy
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
        # Add a header to distinguish from manual command
        full_message = f"⏰ <b>Daily Scheduler Execution</b>\n\n{report_text}"
        send_notification(full_message)
        
        logging.info("[Scheduler] Daily execution completed and report sent.")

    except Exception as e:
        logging.error(f"[Scheduler] Daily Order Job failed: {e}", exc_info=True)
        send_notification(f"⚠️ Scheduler Order Error: {e}")
