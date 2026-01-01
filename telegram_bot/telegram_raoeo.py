# -*- coding: utf-8 -*-
"""
Telegram RAOEO Module

This module handles RAOEO strategy specific Telegram commands and reporting.
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from menu.raoeo.raoeo import build_raoeo_report, execute_orders, save_history

# Local cached result for RAOEO
_cached_result = None

def format_raoeo_report(report: dict) -> str:
    """Format RAOEO report for Telegram message."""
    lines = []
    if report.get("executed_today"):
        entry = report["executed_today"]
        lines.append(f"📊 *RAOEO Executed - {entry['date']}*")
        lines.append(f"Target: `{entry['config']['target']}` @ {entry['config']['exchange']}")
        lines.append(f"Holdings: {entry['holdings']['qty']} shares @ ${entry['holdings']['avg_price']:.2f}")
        lines.append("")
        lines.append("✅ *Executed Orders:*")
        for i, order in enumerate(entry['orders'], 1):
            emoji = "🟢" if order['type'].lower() == 'buy' else "🔴"
            lines.append(f"  {emoji} {order['type'].upper()} {order['qty']} @ ${order['price']:.2f}")

    elif report.get("error") and not report.get("current_result"):
        lines.append(f"⚠️ *Error:* {report['error']}")

    elif report.get("current_result"):
        result = report["current_result"]
        if result.get('error'):
            lines.append(f"⚠️ *Error:* {result['error']}")
        elif not result.get('orders'):
            lines.append(f"📊 *RAOEO - {result['date']}*")
            lines.append("No orders calculated for today.")
        else:
            lines.append(f"📊 *RAOEO Order Calculation - {result['date']}*")
            lines.append(f"Target: `{result['config']['target']}` @ {result['config']['exchange']}")
            lines.append(f"Current Price: ${result['holdings']['cur_price']:.2f}")
            lines.append(f"Holdings: {result['holdings']['qty']} @ ${result['holdings']['avg_price']:.2f}")
            lines.append("")
            lines.append("📋 *Pending Orders:*")
            for i, order in enumerate(result['orders'], 1):
                emoji = "🟢" if order['type'].lower() == 'buy' else "🔴"
                lines.append(f"  {emoji} {order['type'].upper()} {order['qty']} @ ${order['price']:.2f}")
                lines.append(f"      _{order['desc']}_")

    return "\n".join(lines)

async def cmd_raoeo_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /raoeo_report."""
    global _cached_result
    from .telegram_bot import wrap_reply

    report = build_raoeo_report()
    _cached_result = report.get("current_result")

    msg = format_raoeo_report(report)
    if msg:
        await wrap_reply(update, msg, parse_mode='Markdown')
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
        lines = ["📋 *Execution Results:*"]
        success_count = 0
        for i, res in enumerate(exec_results, 1):
            status = "✅" if res['success'] else "❌"
            if res['success']:
                success_count += 1
            o = res['order']
            lines.append(f"{status} {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}")

        save_history(_cached_result)
        lines.append(f"\n💾 Saved to history. ({success_count}/{len(orders)} succeeded)")
        _cached_result = None
        await wrap_reply(update, "\n".join(lines), parse_mode='Markdown')

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
        "/raoeo\\_report \\- Current RAOEO status\n"
        "/raoeo\\_order \\- Execute RAOEO orders"
    )
