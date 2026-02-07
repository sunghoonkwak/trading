# -*- coding: utf-8 -*-
"""
Scheduler Order Service
Handles daily order reporting and notifications (RAOEO, Value Averaging).
"""
import logging
from telegram_bot.telegram_utils import send_notification
from strategy import raoeo
from strategy import value_averaging
from telegram_bot.telegram_raoeo import format_raoeo_report
from telegram_bot.telegram_portfolio import format_va_report

def run_daily_order_report():
    """
    Execute daily order update routine (typically scheduled for evening).
    Sends RAOEO and Value Averaging reports via Telegram (with Auto-Execution).
    """
    import logging
    from datetime import datetime
    import pytz

    logging.info("[Scheduler] Starting daily order report & execution job.")
    try:
        report_parts = []

        # 1. RAOEO Report & Execution
        try:
            raoeo_report = raoeo.get_daily_report()

            # Check for pending orders and if NOT already executed today
            pending_orders = raoeo_report.get("pending_orders", [])
            executed_today = raoeo_report.get("executed_today")
            failed_orders = raoeo_report.get("failed_orders", [])
            is_holiday = raoeo_report.get("status") == "market_holiday"

            # If we have pending orders (including retries) and it's not marked as fully executed today
            if (pending_orders or failed_orders) and not executed_today and not is_holiday:
                logging.info(f"[Scheduler] Executing RAOEO orders: {len(pending_orders)} pending, {len(failed_orders)} failed")

                # Combine pending and failed into executable list (get_daily_report separates them)
                # Note: raoeo.execute_orders handles the list.
                # We should prefer 'pending_orders' from the report if it includes everything needing execution.
                # However, get_daily_report splits them.
                # Logic in telegram_raoeo: "pending_orders" from report are displayed.
                # Let's verify what execute_orders expects. It expects a list of order dicts.

                # In raoeo.py:
                # "pending_orders" includes new ones.
                # "failed_orders" are from history.
                # But get_daily_report's step 3 populates pending_orders from current_result (which includes failed retries).
                # So pending_orders should contain ALL valid orders to execute.

                execution_target = pending_orders

                if execution_target:
                    config = raoeo_report.get("config")
                    exec_results = raoeo.execute_orders(execution_target, config)

                    # Save history
                    # We need to construct the 'result' dict similar to calculation output
                    exec_data = {
                        "date": (raoeo_report.get("current_result") or {}).get("date"),
                        "config": config,
                        "holdings": raoeo_report.get("holdings"),
                        "orders": execution_target,
                        "state": (raoeo_report.get("current_result") or {}).get("state", "unknown")
                    }
                    raoeo.save_history(exec_data, exec_results)

                    # Re-fetch report to reflect execution
                    raoeo_report = raoeo.get_daily_report()

            raoeo_text = format_raoeo_report(raoeo_report)
            report_parts.append(raoeo_text)

        except Exception as e:
            logging.error(f"[Scheduler] Error in RAOEO execution: {e}", exc_info=True)
            report_parts.append(f"⚠️ RAOEO Error: {e}")

        # 2. Value Averaging Report & Execution
        try:
            va_result = value_averaging.get_daily_report()

            # VA returns a list of result objects in 'results'
            # We need to iterate and execute if pending
            results = va_result.get("results", [])
            is_holiday = va_result.get("status") == "market_holiday"
            active_execution = False

            if not is_holiday:
                for res in results:
                    ticker = res.get("target_ticker")
                    already_executed = res.get("already_executed")
                    orders = res.get("orders", [])

                    # If orders exist and NOT already executed, Execute!
                    if orders and not already_executed:
                        active_execution = True
                        executed_flag = False

                        for order in orders:
                            # Execute Single Order
                            logging.info(f"[Scheduler] Executing VA order for {ticker}: {order['qty']} @ {order['price']}")
                            exec_res = value_averaging.execute_single_order(ticker, order)

                            # Save result (per order basis, but save_ticker_result handles day record)
                            value_averaging.save_ticker_result(
                                ticker=ticker,
                                day_count=res.get("day_count", 0),
                                result=exec_res,
                                executed=True
                            )
                            executed_flag = True

                    elif not orders and not already_executed:
                        # No orders needed (Skip)
                        skip_res = {
                            "order": None,
                            "success": True,
                            "message": "Skipped (No order needed)",
                            "type": "skip"
                        }
                        value_averaging.save_ticker_result(
                            ticker=ticker,
                            day_count=res.get("day_count", 0),
                            result=skip_res,
                            executed=True # We 'executed' the check
                        )

            # Re-fetch report after execution to show updated status
            # Only if we did something (execution or skip save)
            # Actually easiest to just re-fetch always if not error
            va_result = value_averaging.get_daily_report()

            va_text = format_va_report(va_result)
            report_parts.append(va_text)

        except Exception as e:
            logging.error(f"[Scheduler] Error in VA execution: {e}", exc_info=True)
            report_parts.append(f"⚠️ VA Error: {e}")

        # Send Combined Message
        full_message = "\n\n".join(report_parts)
        send_notification(full_message)
        logging.info("[Scheduler] Daily order notification sent.")

    except Exception as e:
        logging.error(f"[Scheduler] Daily Order Job failed: {e}")
        send_notification(f"⚠️ Scheduler Order Error: {e}")
