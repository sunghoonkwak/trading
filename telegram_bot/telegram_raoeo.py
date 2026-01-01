# -*- coding: utf-8 -*-
"""
Telegram RAOEO Module

This module handles RAOEO strategy specific Telegram commands and reporting.
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import time
from menu.raoeo.raoeo import build_raoeo_report, execute_orders, save_history

# Local cached result for RAOEO
_cached_result = None
_cached_time = 0

def format_raoeo_report(report: dict) -> str:
    """Format RAOEO report for Telegram with Success/Fail/Pending sections."""
    lines = []
    today_str = report.get("current_result", {}).get("date") or report.get("executed_today", {}).get("date", "Today")
    lines.append(f"📊 <b>RAOEO Status - {today_str}</b>")

    config = None
    holdings = None

    # 1. Gather status from history if exists
    success_orders = []
    failed_orders = []

    # Try to find today's entry in history to show what's already happened
    from menu.raoeo.raoeo import HISTORY_FILE
    import json, os
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                hist = json.load(f)
                today_entry = next((e for e in hist.get('history', []) if e.get('date') == today_str), None)
                if today_entry:
                    config = today_entry.get('config')
                    holdings = today_entry.get('holdings')
                    for o in today_entry.get('orders', []):
                        if o.get('success'):
                            success_orders.append(o)
                        else:
                            failed_orders.append(o)
        except:
            pass

    # 2. Add Pending Section (from current_result)
    pending_orders = []
    if report.get("current_result"):
        res = report["current_result"]
        config = config or res.get('config')
        holdings = holdings or res.get('holdings')
        pending_orders = res.get('orders', [])

    if config:
        lines.append(f"Target: <code>{config['target']}</code> @ {config['exchange']}")
    if holdings:
        lines.append(f"Holdings: {holdings['qty']} @ ${holdings['avg_price']:.2f} (Cur: ${holdings.get('cur_price', 0):.2f})")
    lines.append("")

    # --- Section: Success ---
    if success_orders:
        lines.append("✅ <b>Successfully Executed:</b>")
        for o in success_orders:
            lines.append(f"  • {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}")
        lines.append("")

    # --- Section: Failed ---
    if failed_orders:
        lines.append("❌ <b>Failed Orders (Need Fix):</b>")
        for o in failed_orders:
            err = f" - <i>{o.get('error')}</i>" if o.get('error') else ""
            lines.append(f"  • {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}{err}")
        lines.append("")

    # --- Section: Pending ---
    if pending_orders:
        lines.append("⏳ <b>Orders to Place (Pending):</b>")
        for o in pending_orders:
            lines.append(f"  • {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}")
            lines.append(f"      <i>{o.get('desc', '')}</i>")
        lines.append("")
    elif not success_orders and not failed_orders:
        lines.append("No orders for today.")

    if failed_orders or pending_orders:
        lines.append("💡 <i>Use /raoeo_order to execute pending items.</i>")
    elif success_orders:
        lines.append("✨ <i>All orders completed for today.</i>")

    return "\n".join(lines)


async def cmd_raoeo_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /raoeo_report."""
    global _cached_result
    from .telegram_bot import wrap_reply

    report = build_raoeo_report()
    _cached_result = report.get("current_result")
    global _cached_time
    _cached_time = time.time()

    msg = format_raoeo_report(report)
    if msg:
        await wrap_reply(update, msg, parse_mode='HTML')
    else:
        await wrap_reply(update, "No RAOEO data available.")

async def cmd_raoeo_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /raoeo_order."""
    global _cached_result
    from .telegram_bot import wrap_reply

    report = build_raoeo_report()
    if report.get("executed_today"):
        await wrap_reply(update, "✅ Already executed today. No new orders to place.")
        return

    if not _cached_result:
        await wrap_reply(update, "⚠️ Not calculated. Use /raoeo_report first.")
        return

    # Check cache age (max 5 minutes)
    global _cached_time
    if time.time() - _cached_time > 300: # 300 seconds = 5 minutes
        await wrap_reply(update, "⏱ <b>Order Expired</b>: Calculated data is older than 5 minutes. Please run /raoeo_report again to get current prices.", parse_mode='HTML')
        return

    if _cached_result.get('error'):
        await wrap_reply(update, f"⚠️ Cannot execute: {_cached_result['error']}")
        return

    orders = _cached_result.get('orders', [])
    if not orders:
        await wrap_reply(update, "⚠️ No orders to execute.")
        return

    await wrap_reply(update, f"⏳ Executing {len(orders)} orders...")

    try:
        exec_results = execute_orders(orders, _cached_result['config'])
        lines = ["📋 <b>Execution Results:</b>"]
        success_count = 0
        for i, res in enumerate(exec_results, 1):
            status = "✅" if res['success'] else "❌"
            if res['success']:
                success_count += 1
            o = res['order']
            err_msg = f" ({res['error']})" if not res['success'] and res.get('error') else ""
            lines.append(f"{status} {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}{err_msg}")

        save_history(_cached_result, exec_results)
        lines.append(f"\n💾 Saved to history. ({success_count}/{len(orders)} succeeded)")
        _cached_result = None
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
