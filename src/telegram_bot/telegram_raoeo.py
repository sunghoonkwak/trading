# -*- coding: utf-8 -*-
"""
Telegram RAOEO Module

This module handles RAOEO strategy specific Telegram commands with ConversationHandler
for interactive order confirmation.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    ConversationHandler, CallbackQueryHandler, TypeHandler
)
from .telegram_utils import wrap_reply, wrap_edit, wrap_edit_message

from strategy.raoeo import get_daily_report, execute_all_orders, save_history

# Conversation state
RAOEO_CONFIRM = 0


def format_raoeo_report(report: dict) -> str:
    """Format RAOEO report for Telegram (Multi-Target)."""
    if not report:
        return "⚠️ No RAOEO data available."

    lines = []
    today_str = report.get("date", "Today")
    global_status = report.get("status", "unknown")

    lines.append(f"📊 <b>RAOEO Status - {today_str}</b>")
    if report.get("global_error"):
        lines.append(f"⚠️ Global Error: {report['global_error']}")

    targets = report.get("targets", {})
    if not targets:
        lines.append("No targets configured.")
        return "\n".join(lines)

    # Iterate targets
    for ticker, t_report in targets.items():
        config = t_report.get("config")
        exch = config.get('exchange', 'N/A') if config else 'N/A'

        lines.append(f"\n🔹 <b>{ticker} @ {exch}</b>")

        holdings = t_report.get("holdings") or {}
        cur_price = t_report.get("cur_price", 0)

        # Info Line
        if config:
             seed = float(config.get('seed', 0))
             duration = int(config.get('duration', 1))
             daily_budget = seed / duration if duration > 0 else 0
             lines.append(f"  Budget: ${daily_budget:.2f}/day (${seed:,.0f} / {duration}d)")

        if holdings:
             lines.append(f"  Holdings: {holdings.get('qty', 0)} @ ${holdings.get('avg_price', 0):.2f} (Cur: ${cur_price:.2f})")

        # Orders
        success_orders = t_report.get("success_orders", [])
        failed_orders = t_report.get("failed_orders", [])
        pending_orders = t_report.get("pending_orders", []) # These are new calculated ones

        # Section: Success
        if success_orders:
            lines.append("  ✅ <b>Completed:</b>")
            for o in success_orders:
                lines.append(f"    • {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}")

        # Section: Failed (Retry)
        if failed_orders:
            lines.append("  🔄 <b>Failed → Retry:</b>")
            for o in failed_orders:
                err = f" - <i>{o.get('error', '')[:20]}</i>" if o.get('error') else ""
                lines.append(f"    • {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}{err}")

        # Section: Pending
        # Filter out if already in failed set (though logic usually separates them)
        if pending_orders:
            lines.append("  ⏳ <b>Pending:</b>")
            for o in pending_orders:
                lines.append(f"    • {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}")

        if t_report.get("status") == "market_holiday":
            lines.append("  🚫 <b>Market Holiday</b>")
        elif not (success_orders or failed_orders or pending_orders):
            lines.append("  - No orders today.")

    lines.append("")

    # Global Summary
    if global_status == "market_holiday":
        pass # lines.append("🚫 <b>휴장일</b> - 주문 비활성화")

    # Check if executable
    has_executable = False
    for t_report in targets.values():
        if t_report.get("pending_orders") or t_report.get("failed_orders"):
             has_executable = True
             break

    if has_executable:
        lines.append("<i>Execute all pending/failed orders?</i>")
    elif global_status == "executed":
        lines.append("✨ <i>All tasks completed.</i>")

    return "\n".join(lines)


def build_raoeo_keyboard(has_orders: bool) -> InlineKeyboardMarkup:
    """Build Yes/No keyboard for RAOEO confirmation."""
    if has_orders:
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes", callback_data="raoeo_yes"),
                InlineKeyboardButton("❌ No", callback_data="raoeo_no")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    return None


async def cmd_raoeo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /raoeo - RAOEO status and order execution."""
    logging.info(f"[TG] /raoeo from user {update.effective_user.id}")

    try:
        report = get_daily_report()
    except Exception as e:
        logging.error(f"[TG] build_raoeo_report() failed: {e}", exc_info=True)
        await wrap_reply(update, f"⚠️ Error building report: {e}")
        return ConversationHandler.END

    if not report:
        logging.warning("[TG] build_raoeo_report() returned None or empty")
        await wrap_reply(update, "⚠️ RAOEO report unavailable. Check configuration.")
        return ConversationHandler.END

    # Cache report in user_data
    context.user_data['raoeo_report'] = report

    # Format message
    msg = format_raoeo_report(report)

    # Check if there are executable orders globally
    has_orders = False
    if report.get("targets"):
        for t_report in report["targets"].values():
            if t_report.get("pending_orders") or t_report.get("failed_orders"):
                has_orders = True
                break

    # Holiday check - disable orders
    if report.get("status") == "market_holiday":
        has_orders = False

    # Also if already fully executed, no need to show yes/no (though logic above handles it via pending/failed checks)

    # Build keyboard
    keyboard = build_raoeo_keyboard(has_orders)

    sent_msg = await wrap_reply(update, msg, parse_mode='HTML', reply_markup=keyboard)
    if sent_msg:
        context.user_data['raoeo_msg_id'] = sent_msg.message_id

    return RAOEO_CONFIRM if has_orders else ConversationHandler.END


async def handle_raoeo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle RAOEO Yes/No button clicks."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    logging.info(f"[TG] RAOEO Callback: {callback_data}")

    report = context.user_data.get('raoeo_report')

    if callback_data == "raoeo_no":
        await wrap_edit(update, "❌ <b>Order Cancelled.</b>", parse_mode='HTML')
        context.user_data.pop('raoeo_report', None)
        context.user_data.pop('raoeo_msg_id', None)
        return ConversationHandler.END

    if callback_data == "raoeo_yes":
        if not report:
            await wrap_edit(update, "⚠️ Session expired. Please run /raoeo again.", parse_mode='HTML')
            return ConversationHandler.END

        # Re-verify executable orders
        # In multi-target, we need to gather all pending/failed from report to pass to execute
        # OR just pass the whole report to a new execute_all_orders function?
        # Let's see what we did in raoeo.py.
        # I added execute_all_orders(calculated_result) in raoeo.py.
        # But wait, execute_all_orders expects the format returned by calculate_orders.
        # get_daily_report structure is slightly different (nested keys match, but we need to ensure orders are there).
        # In get_daily_report, we populated "pending_orders" in t_report.
        # But execute_all_orders uses 'orders' key in target data if I recall correctly?
        # Let's double check execute_all_orders implementation in raoeo.py I just wrote.
        # It iterates targets -> orders.
        # In get_daily_report, I put new orders in "pending_orders" and failed in "failed_orders".
        # So I might need to construct a "execution payload" here.

        # Construct execution payload
        execution_payload = {
            "date": report.get("date"),
            "targets": {}
        }

        exec_count = 0

        for ticker, t_report in report.get("targets", {}).items():
            to_exec = []
            to_exec.extend(t_report.get("pending_orders", []))
            to_exec.extend(t_report.get("failed_orders", [])) # Retry these too

            if to_exec:
                execution_payload["targets"][ticker] = {
                    "config": t_report.get("config"),
                    "orders": to_exec
                }
                exec_count += len(to_exec)

        if exec_count == 0:
            await wrap_edit(update, "⚠️ No orders to execute.", parse_mode='HTML')
            context.user_data.pop('raoeo_report', None)
            return ConversationHandler.END

        # Execute orders
        try:
            # We use execute_all_orders from raoeo.py
            exec_results_map = execute_all_orders(execution_payload)

            # Update report display
            lines = [format_raoeo_report(report), "", "─" * 20, "<b>Execution Result:</b>"]

            total_success = 0

            for ticker, res_list in exec_results_map.items():
                if not res_list: continue
                lines.append(f"🔹 {ticker}:")
                for res in res_list:
                    status = "✅" if res['success'] else "❌"
                    if res['success']: total_success += 1
                    o = res['order']
                    err_msg = f" ({res['error']})" if not res['success'] and res.get('error') else ""
                    lines.append(f"  {status} {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}{err_msg}")

            # Save to history
            # save_history expects (calculated_result, execution_summary)
            # calculated_result should have the orders we tried to execute.
            # execution_summary is the map ticker -> result list
            save_history(execution_payload, exec_results_map)

            lines.append(f"\n💾 Saved. <b>{total_success}/{exec_count} succeeded</b>")
            await wrap_edit(update, "\n".join(lines), parse_mode='HTML')

        except Exception as e:
            logging.error(f"[TG] RAOEO Order execution failed: {e}", exc_info=True)
            await wrap_edit(update, f"❌ Execution failed: {e}", parse_mode='HTML')

        context.user_data.pop('raoeo_report', None)
        context.user_data.pop('raoeo_msg_id', None)
        return ConversationHandler.END

    return RAOEO_CONFIRM


async def raoeo_timeout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle RAOEO conversation timeout."""
    logging.info("[TG] RAOEO session timed out")
    context.user_data.pop('raoeo_report', None)

    # Try to edit the message if possible
    if 'raoeo_msg_id' in context.user_data:
        try:
            from .telegram_bot import _chat_id
            if _chat_id:
                await wrap_edit_message(
                    chat_id=_chat_id,
                    message_id=context.user_data.get('raoeo_msg_id'),
                    text="⏱️ <i>RAOEO session expired.</i>",
                    parse_mode='HTML'
                )
        except Exception:
            pass
        context.user_data.pop('raoeo_msg_id', None)

    return ConversationHandler.END


def register_raoeo_handlers(app: Application):
    """Register RAOEO command handlers to the application."""
    raoeo_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("raoeo", cmd_raoeo)],
        states={
            RAOEO_CONFIRM: [
                CallbackQueryHandler(handle_raoeo_callback, pattern=r'^raoeo_')
            ],
            ConversationHandler.TIMEOUT: [TypeHandler(object, raoeo_timeout_handler)]
        },
        fallbacks=[],
        conversation_timeout=60,
        per_message=False,
    )
    app.add_handler(raoeo_conv_handler)


def get_raoeo_commands_desc() -> str:
    """Return RAOEO command descriptions for init message."""
    return "/raoeo - RAOEO status & order"
