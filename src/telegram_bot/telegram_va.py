# -*- coding: utf-8 -*-
"""
Telegram Value Averaging Module

This module handles Value Averaging (VA) specific Telegram commands with
bulk execution capability.
"""
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    ConversationHandler, CallbackQueryHandler, TypeHandler
)
from .telegram_utils import wrap_reply, wrap_edit, wrap_edit_message
from strategy import value_averaging

# Conversation states
VA_CONFIRM = 1

def get_va_status_lines(r: dict) -> list[str]:
    """Generate status lines for a single VA result."""
    lines = []
    ticker = r.get("target_ticker", "Unknown")
    buy_amt = r.get("daily_target_amount", 0)

    if r.get("error"):
        lines.append(f"⚠️ <b>{ticker}</b>: {r['error']}")
        return lines

    day = r.get("day_count", 0)
    tgt_val = r.get("target_value_accumulated", 0)
    cur_val = r.get("current_value", 0)
    diff_pct = ((cur_val - tgt_val) / tgt_val * 100) if tgt_val > 0 else 0.0

    info_str = f"(Day {day} | Target ${tgt_val:,.0f} | Cur ${cur_val:,.0f} | {diff_pct:+.1f}%)"

    if r.get("already_executed"):
         executed_orders = r.get("executed_orders", [])
         if executed_orders:
             lines.append(f"✅ <b>{ticker}</b> {info_str}")
             for o in executed_orders:
                 qty = o.get('qty')
                 price = o.get('price')
                 suffix = "share" if qty == 1 else "shares"
                 o_type = o.get('type', 'buy')
                 side = "Sell" if "sell" in o_type.lower() else "Buy"
                 lines.append(f"   └ {side} {qty} {suffix} (${price:,.2f})")
         else:
             lines.append(f"⚠️ <b>{ticker}</b> {info_str}")
             lines.append(f"   └ Error: Marked executed but no orders found (Unexpected Skip)")
    else:
         orders = r.get("orders", [])
         if orders:
              target_txt = "Sell" if buy_amt < 0 else "Buy"
              abs_amt = abs(buy_amt)
              lines.append(f"🔹 <b>{ticker}</b> {info_str}")
              lines.append(f"   └ {target_txt} ${abs_amt:,.2f}")
              for o in orders:
                  qty = o['qty']
                  price = o['price']
                  suffix = "share" if qty == 1 else "shares"
                  o_type = o.get('type', 'buy')
                  side = "Sell" if "sell" in o_type.lower() else "Buy"
                  lines.append(f"   └ {side} {qty} {suffix} (${price:,.2f})")
         elif r.get("current_price", 0) > 0:
              threshold = r.get("threshold_rate", 0.15)
              lines.append(f"⏸️ <b>{ticker}</b> {info_str}")
              lines.append(f"   └ Hold (Diff inside ±{int(threshold*100)}%)")
         else:
              lines.append(f"⚠️ <b>{ticker}</b>: Price unavailable")

    return lines


def format_va_report(data: dict) -> str:
    """Format full daily VA report for scheduler."""
    if data.get("error"):
        return f"⚠️ <b>Value Averaging Error:</b> {data['error']}"

    results = data.get("results", [])
    if not results:
        return "⚠️ <b>Value Averaging Error:</b> No results found (Check configuration)."

    lines = [f"📈 <b>Value Averaging</b> ({data.get('date', 'N/A')})", ""]

    for r in results:
        lines.extend(get_va_status_lines(r))

    if data.get("status") == "market_holiday":
        lines.append("")
        lines.append("🚫 <b>Market Holiday</b>")

    return "\n".join(lines)


async def cmd_value_averaging(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /value_averaging - Value Averaging (Bulk Execution)."""
    logging.info(f"[TG] /value_averaging from user {update.effective_user.id}")

    # Calculate order for all tickers
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(
        None, value_averaging.get_daily_report
    )

    if res.get("error"):
        await wrap_reply(update, f"⚠️ <b>Error:</b> {res['error']}", parse_mode='HTML')
        return ConversationHandler.END

    results = res.get("results", [])
    if not results:
        await wrap_reply(update, "⚠️ <b>No targets found (or all disabled).</b>", parse_mode='HTML')
        return ConversationHandler.END

    is_holiday = (res.get("status") == "market_holiday")
    pending_results = []

    # Filter pending orders
    if not is_holiday:
        for r in results:
            if r.get("error"): continue
            already_exec = r.get("already_executed")
            if r.get('orders') and not already_exec:
                pending_results.append(r)

    # Generate Report Lines
    lines = [f"📈 <b>Value Averaging</b> ({res.get('date', 'N/A')})", ""]
    for r in results:
        lines.extend(get_va_status_lines(r))

    if is_holiday:
        lines.append("")
        lines.append("🚫 <b>Market Holiday</b>")
        await wrap_reply(update, "\n".join(lines), parse_mode='HTML')
        return ConversationHandler.END

    if not pending_results:
        # No actions needed
        lines.append("")
        lines.append("✅ <b>All caught up! No orders to execute.</b>")
        await wrap_reply(update, "\n".join(lines), parse_mode='HTML')
        return ConversationHandler.END

    # If actions needed, show Execute All button
    lines.append("")
    lines.append(f"<b>ready to execute {len(pending_results)} orders?</b>")

    keyboard = [
        [
            InlineKeyboardButton("🚀 Execute All", callback_data="va_exec_all"),
            InlineKeyboardButton("❌ Cancel", callback_data="va_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sent_msg = await wrap_reply(update, "\n".join(lines), parse_mode='HTML', reply_markup=reply_markup)

    # Save context for callback
    context.user_data['va_pending'] = pending_results
    if sent_msg:
        context.user_data['va_msg_id'] = sent_msg.message_id

    return VA_CONFIRM


async def handle_va_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Value Averaging bulk execution buttons."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    logging.info(f"[TG] VA Callback: {callback_data}")

    if callback_data == "va_cancel":
        await wrap_edit(update, "❌ <b>Value Averaging Cancelled.</b>", parse_mode='HTML')
        context.user_data.pop('va_pending', None)
        return ConversationHandler.END

    if callback_data == "va_exec_all":
        pending_results = context.user_data.get('va_pending', [])
        if not pending_results:
             await wrap_edit(update, "⚠️ <b>Session expired or no orders.</b>", parse_mode='HTML')
             return ConversationHandler.END

        await wrap_edit(update, "⏳ <b>Executing orders...</b>", parse_mode='HTML')

        loop = asyncio.get_running_loop()
        exec_log = []
        success_count = 0

        for r in pending_results:
            ticker = r.get("target_ticker")
            day_count = r.get("day_count")
            orders = r.get("orders", [])

            if not orders: continue

            # Execute first order (usually one per ticker)
            order = orders[0]
            result = await loop.run_in_executor(
                None, value_averaging.execute_single_order, ticker, order
            )

            executed = result.get('success', False)

            # Save history
            await loop.run_in_executor(
                None, value_averaging.save_ticker_result, ticker, day_count, result, executed
            )

            # Log result
            if executed:
                success_count += 1
                o_type = order.get('type', 'buy')
                side = "Sell" if "sell" in o_type.lower() else "Buy"
                qty = order.get('qty')
                price = order.get('price')
                exec_log.append(f"✅ <b>{ticker}</b>: {side} {qty} @ ${price:,.2f} (Success)")
            else:
                exec_log.append(f"❌ <b>{ticker}</b>: {result.get('message', 'Failed')}")

        # Final Report
        lines = ["🚀 <b>Value Averaging Execution Complete</b>", ""]
        lines.extend(exec_log)
        lines.append("")
        lines.append(f"<b>Total Executed: {success_count}/{len(pending_results)}</b>")

        await wrap_edit(update, "\n".join(lines), parse_mode='HTML')

        context.user_data.pop('va_pending', None)
        return ConversationHandler.END

    return ConversationHandler.END


async def va_timeout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle VA conversation timeout."""
    logging.info("[TG] VA session timed out")
    context.user_data.pop('va_pending', None)

    if 'va_msg_id' in context.user_data:
        chat_id = update.effective_chat.id if update and update.effective_chat else context.user_data.get('chat_id')
        try:
            await wrap_edit_message(
                chat_id=chat_id,
                message_id=context.user_data.get('va_msg_id'),
                text="⏱️ <i>VA session expired.</i>",
                parse_mode='HTML'
            )
        except Exception:
            pass
        context.user_data.pop('va_msg_id', None)
    return ConversationHandler.END


def register_va_handlers(app: Application):
    """Register VA command handlers."""
    va_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("value_averaging", cmd_value_averaging)],
        states={
            VA_CONFIRM: [
                CallbackQueryHandler(handle_va_callback, pattern=r'^va_')
            ],
            ConversationHandler.TIMEOUT: [TypeHandler(object, va_timeout_handler)]
        },
        fallbacks=[],
        conversation_timeout=60,
        per_message=False,
    )
    app.add_handler(va_conv_handler)


def get_va_commands_desc() -> str:
    """Return VA command descriptions for init message."""
    return "/value_averaging - Value Averaging order"
