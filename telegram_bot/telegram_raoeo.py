# -*- coding: utf-8 -*-
"""
Telegram RAOEO Module

This module handles RAOEO strategy specific Telegram commands and reporting.
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from .telegram_utils import wrap_reply

import time
from menu.raoeo.raoeo import build_raoeo_report, execute_orders, save_history

# Local cached report for RAOEO
_cached_report = None
_cached_time = 0

def format_raoeo_report(report: dict) -> str:
    """Format RAOEO report for Telegram with Success/Failed sections."""
    if not report:
        return "⚠️ No RAOEO data available."

    lines = []
    today_str = (report.get("current_result") or {}).get("date") or (report.get("executed_today") or {}).get("date", "Today")
    lines.append(f"📊 <b>RAOEO Status - {today_str}</b>")

    # Get pre-calculated values from report
    config = report.get("config")
    holdings = report.get("holdings") or {}
    cur_price = report.get("cur_price", 0)
    success_orders = report.get("success_orders", [])
    failed_orders = report.get("failed_orders", [])
    pending_orders = report.get("pending_orders", [])

    if config:
        lines.append(f"Target: <code>{config['target']}</code> @ {config['exchange']}")
    if holdings:
        lines.append(f"Holdings: {holdings.get('qty', 0)} @ ${holdings.get('avg_price', 0):.2f} (Cur: ${cur_price:.2f})")
    if config:
        # Calculate and show daily budget
        seed = float(config.get('seed', 0))
        duration = int(config.get('duration', 1))
        daily_budget = seed / duration if duration > 0 else 0
        lines.append(f"Budget: ${daily_budget:.2f}/day (${seed:,.0f} / {duration} days)")
    lines.append("")

    # --- Section: Success ---
    if success_orders:
        lines.append("✅ <b>Completed:</b>")
        for o in success_orders:
            lines.append(f"  • {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}")
        lines.append("")

    # --- Section: Failed (with retry indicator) ---
    if failed_orders:
        lines.append("🔄 <b>Failed → Retry:</b>")
        for o in failed_orders:
            err = f" - <i>{o.get('error', '')[:30]}</i>" if o.get('error') else ""
            lines.append(f"  • {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}{err}")
        lines.append("")

    # --- Section: New Pending (not from failed retry) ---
    failed_types = {o.get('type') for o in failed_orders}
    new_pending = [o for o in pending_orders if o.get('type') not in failed_types]
    if new_pending:
        lines.append("⏳ <b>Pending:</b>")
        for o in new_pending:
            lines.append(f"  • {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}")
        lines.append("")

    if not success_orders and not failed_orders and not pending_orders:
        lines.append("No orders for today.")

    if failed_orders or pending_orders:
        lines.append("💡 <i>Use /raoeo_order to execute.</i>")
    elif success_orders:
        lines.append("✨ <i>All orders completed for today.</i>")

    return "\n".join(lines)


async def cmd_raoeo_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /raoeo_report."""
    global _cached_report, _cached_time

    try:
        report = build_raoeo_report()
    except Exception as e:
        logging.error(f"[Telegram] build_raoeo_report() failed: {e}", exc_info=True)
        await wrap_reply(update, f"⚠️ Error building report: {e}")
        return

    if not report:
        logging.warning("[Telegram] build_raoeo_report() returned None or empty")
        await wrap_reply(update, "⚠️ RAOEO report unavailable. Check configuration.")
        return

    _cached_report = report
    _cached_time = time.time()

    msg = format_raoeo_report(report)
    await wrap_reply(update, msg, parse_mode='HTML')


async def cmd_raoeo_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /raoeo_order."""
    global _cached_report, _cached_time

    # Check if we have cached report
    if not _cached_report:
        await wrap_reply(update, "⚠️ Not calculated. Use /raoeo_report first.")
        return

    # Check cache age (max 5 minutes)
    if time.time() - _cached_time > 300:
        await wrap_reply(update, "⏱ <b>Order Expired</b>: Calculated data is older than 5 minutes. Please run /raoeo_report again to get current prices.", parse_mode='HTML')
        return

    # Check if already executed today
    if _cached_report.get("executed_today"):
        await wrap_reply(update, "✅ Already executed today. No new orders to place.")
        return

    # Check for errors
    if _cached_report.get("error"):
        await wrap_reply(update, f"⚠️ Cannot execute: {_cached_report['error']}")
        return

    # Get pending orders
    pending_orders = _cached_report.get("pending_orders", [])
    if not pending_orders:
        await wrap_reply(update, "⚠️ No pending orders to execute.")
        return

    await wrap_reply(update, f"⏳ Executing {len(pending_orders)} orders...")

    try:
        config = _cached_report.get("config")
        exec_results = execute_orders(pending_orders, config)
        lines = ["📋 <b>Execution Results:</b>"]
        success_count = 0
        for i, res in enumerate(exec_results, 1):
            status = "✅" if res['success'] else "❌"
            if res['success']:
                success_count += 1
            o = res['order']
            err_msg = f" ({res['error']})" if not res['success'] and res.get('error') else ""
            lines.append(f"{status} {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}{err_msg}")

        # Create result dict for save_history
        exec_data = {
            "date": (_cached_report.get("current_result") or {}).get("date"),
            "config": config,
            "holdings": _cached_report.get("holdings"),
            "orders": pending_orders,
            "state": (_cached_report.get("current_result") or {}).get("state", "unknown")
        }
        save_history(exec_data, exec_results)
        lines.append(f"\n💾 Saved to history. ({success_count}/{len(pending_orders)} succeeded)")
        _cached_report = None
        await wrap_reply(update, "\n".join(lines), parse_mode='HTML')

    except Exception as e:
        logging.error(f"[Telegram] RAOEO Order execution failed: {e}")
        await wrap_reply(update, f"❌ Execution failed: {e}")

def register_raoeo_handlers(app: Application):
    """Register RAOEO command handlers to the application."""
    app.add_handler(CommandHandler("raoeo_report", cmd_raoeo_report))
    app.add_handler(CommandHandler("raoeo_order", cmd_raoeo_order))

def get_raoeo_commands_desc() -> str:
    """Return RAOEO command descriptions for init message."""
    return (
        "/raoeo_report - Current RAOEO status\n"
        "/raoeo_order - Execute RAOEO orders"
    )
