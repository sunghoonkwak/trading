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
from telegram_bot.telegram_va import format_va_report

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

            # RAOEO Multi-Target Execution Logic
            # We need to gather executable orders from all targets
            execution_payload = {
                "date": raoeo_report.get("date"),
                "targets": {}
            }

            has_executable = False
            targets_report = raoeo_report.get("targets", {})

            for ticker, t_report in targets_report.items():
                if t_report.get("status") == "market_holiday":
                    continue

                p_orders = t_report.get("pending_orders", [])
                f_orders = t_report.get("failed_orders", [])

                # Check for pending orders and failed orders
                if (p_orders or f_orders) and t_report.get("status") != "executed":
                    to_exec = []
                    to_exec.extend(p_orders)
                    to_exec.extend(f_orders)

                    if to_exec:
                        execution_payload["targets"][ticker] = {
                            "config": t_report.get("config"),
                            "orders": to_exec
                        }
                        has_executable = True

            if raoeo_report.get("status") == "market_holiday":
                has_executable = False
                logging.info("[Scheduler] RAOEO: Market Holiday, skipping.")

            if has_executable:
                logging.info(f"[Scheduler] Executing RAOEO orders for targets: {list(execution_payload['targets'].keys())}")

                # Execute All
                exec_results_map = raoeo.execute_all_orders(execution_payload)

                # Save History
                raoeo.save_history(execution_payload, exec_results_map)

                # Re-fetch report for notification
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
