# -*- coding: utf-8 -*-
"""
Scheduler Order Service
Handles daily order reporting and notifications (RAOEO, Value Averaging).
"""
import logging
from telegram_bot.telegram_utils import send_notification
from menu.raoeo import raoeo
from menu.portfolio import value_averaging
from telegram_bot.telegram_raoeo import format_raoeo_report
from telegram_bot.telegram_portfolio import format_va_report

def run_daily_order_report():
    """
    Execute daily order update routine (typically scheduled for evening).
    Sends RAOEO and Value Averaging reports via Telegram.
    """
    logging.info("[Scheduler] Starting daily order report job.")
    try:
        report_parts = []

        # 1. RAOEO Report
        try:
            raoeo_report = raoeo.get_daily_report()
            raoeo_text = format_raoeo_report(raoeo_report)
            report_parts.append(raoeo_text)
        except Exception as e:
            logging.error(f"Error generating RAOEO report: {e}")
            report_parts.append(f"⚠️ RAOEO Error: {e}")

        # 2. Value Averaging Report
        try:
            va_result = value_averaging.get_daily_report()
            va_text = format_va_report(va_result)
            report_parts.append(va_text)
        except Exception as e:
            logging.error(f"Error generating VA report: {e}")
            report_parts.append(f"⚠️ VA Error: {e}")

        # Send Combined Message
        full_message = "\n" + ("="*25) + "\n\n".join(report_parts)
        send_notification(full_message)
        logging.info("[Scheduler] Daily order notification sent.")

    except Exception as e:
        logging.error(f"[Scheduler] Daily Order Job failed: {e}")
        send_notification(f"⚠️ Scheduler Order Error: {e}")
