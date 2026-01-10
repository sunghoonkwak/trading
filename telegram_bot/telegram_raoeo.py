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

from menu.raoeo.raoeo import build_raoeo_report, execute_orders, save_history
from utils import is_market_holiday

# Conversation state
RAOEO_CONFIRM = 0


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
        lines.append("<i>Execute these orders?</i>")
    elif success_orders:
        lines.append("✨ <i>All orders completed for today.</i>")

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
        report = build_raoeo_report()
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

    # Check if there are executable orders
    pending_orders = report.get("pending_orders", [])
    failed_orders = report.get("failed_orders", [])
    has_orders = bool(pending_orders or failed_orders) and not report.get("executed_today")

    # Holiday check - show warning and disable orders
    if is_market_holiday("NYSE"):
        msg += "\n\n🚫 <b>휴장일</b> - 주문 비활성화"
        has_orders = False

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

        # Get pending orders (include failed orders for retry)
        pending_orders = report.get("pending_orders", [])
        if not pending_orders:
            await wrap_edit(update, "⚠️ No orders to execute.", parse_mode='HTML')
            context.user_data.pop('raoeo_report', None)
            return ConversationHandler.END

        # Execute orders
        try:
            config = report.get("config")
            exec_results = execute_orders(pending_orders, config)

            lines = [format_raoeo_report(report), "", "─" * 20, "<b>Execution Result:</b>"]
            success_count = 0

            for res in exec_results:
                status = "✅" if res['success'] else "❌"
                if res['success']:
                    success_count += 1
                o = res['order']
                err_msg = f" ({res['error']})" if not res['success'] and res.get('error') else ""
                lines.append(f"{status} {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}{err_msg}")

            # Save to history
            exec_data = {
                "date": (report.get("current_result") or {}).get("date"),
                "config": config,
                "holdings": report.get("holdings"),
                "orders": pending_orders,
                "state": (report.get("current_result") or {}).get("state", "unknown")
            }
            save_history(exec_data, exec_results)
            lines.append(f"\n💾 Saved. <b>{success_count}/{len(pending_orders)} succeeded</b>")

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
