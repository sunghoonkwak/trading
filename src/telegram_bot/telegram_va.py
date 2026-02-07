# -*- coding: utf-8 -*-
"""
Telegram Value Averaging Module

This module handles Value Averaging (VA) specific Telegram commands with
sequential confirmation processing.
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

def format_va_single_ticker(result: dict, idx: int, total: int) -> str:
    """Format a single ticker's Value Averaging result for Telegram."""
    if result.get("error"):
        return f"⚠️ <b>{result.get('target_ticker', 'Unknown')}:</b> {result['error']}"

    target_ticker = result.get("target_ticker", "N/A")
    day_count = result.get("day_count", 0)
    daily_budget = result.get("daily_budget", 0)
    target_weight = result.get("target_weight", 0) * 100
    current_price = result.get("current_price", 0)
    buy_amount = result.get("daily_target_amount", 0)
    orders = result.get("orders", [])
    already_executed = result.get("already_executed", False)
    executed_orders = result.get("executed_orders", [])

    lines = [
        f"📈 <b>Value Averaging</b> ({idx + 1}/{total})",
        "",
        f"── <b>{target_ticker}</b> ──",
    ]

    # Only consider it executed if we actually placed orders (not just skipped)
    real_orders = [o for o in executed_orders if o.get('type') != 'skip']
    real_execution = already_executed and real_orders

    if real_execution:
        lines.append(f"✅ <i>Executed today</i>")
        for o in executed_orders:
            o_qty = o.get('qty', 0)
            o_price = o.get('price', 0)
            o_type = o.get('order_type', 'LOC')
            lines.append(f"   > {o_qty} qty @ ${o_price:,.2f} ({o_type})")
    else:
        lines.append(f"Day: {day_count} | Weight: {target_weight:.1f}%")
        lines.append(f"Price: ${current_price:,.2f} | Budget: ${daily_budget:,.2f}")
        lines.append(f"Buy Amount: <b>${buy_amount:,.2f}</b>")

        if current_price <= 0:
            lines.append("⚠️ <i>Price unavailable</i>")
        elif orders:
            for o in orders:
                o_type = o.get('order_type', 'LOC')
                lines.append(f"📋 {o['qty']} qty @ ${o['price']:.2f} ({o_type})")
            lines.append("")
            lines.append("<i>Execute order?</i>")
        else:
            lines.append("✅ <i>No order needed</i>")
            lines.append("")

    return "\n".join(lines)


def format_va_report(data: dict) -> str:
    """Format full daily VA report for scheduler."""
    if data.get("error"):
        return f"⚠️ <b>Value Averaging Error:</b> {data['error']}"

    results = data.get("results", [])
    if not results:
        return "⚠️ <b>Value Averaging Error:</b> No results found (Check configuration)."

    lines = [f"📈 <b>Value Averaging</b> ({data.get('date', 'N/A')})", ""]

    for r in results:
        ticker = r.get("target_ticker", "Unknown")
        buy_amt = r.get("daily_target_amount", 0)

        if r.get("error"):
            lines.append(f"⚠️ <b>{ticker}</b>: {r['error']}")
            continue

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
                  lines.append(f"⏸️ <b>{ticker}</b> {info_str}")
                  lines.append(f"   └ Hold (Diff inside ±15%)")
             else:
                  lines.append(f"⚠️ <b>{ticker}</b>: Price unavailable")

    if data.get("status") == "market_holiday":
        lines.append("")
        lines.append("🚫 <b>휴장일 (Market Closed)</b>")

    return "\n".join(lines)


def build_va_single_keyboard(has_order: bool, no_order_needed: bool, is_holiday: bool = False) -> InlineKeyboardMarkup:
    """Build keyboard for single ticker VA confirmation."""
    if is_holiday:
        return None

    if has_order:
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes", callback_data="va_yes"),
                InlineKeyboardButton("❌ No", callback_data="va_no")
            ]
        ]
    else:
        return None

    return InlineKeyboardMarkup(keyboard)


async def cmd_value_average(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /value_average - Value Averaging (sequential processing)."""
    logging.info(f"[TG] /value_average from user {update.effective_user.id}")

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
        await wrap_reply(update, "⚠️ <b>No strategies configured.</b>", parse_mode='HTML')
        return ConversationHandler.END

    is_holiday = (res.get("status") == "market_holiday")
    pending_results = []
    if not is_holiday:
        for r in results:
            if r.get("error"): continue
            already_exec = r.get("already_executed")
            if r.get('orders') and not already_exec:
                pending_results.append(r)

    if not pending_results:
        lines = [f"📈 <b>Value Averaging</b> ({res.get('date', 'N/A')})", ""]
        for r in results:
            ticker = r.get("target_ticker", "Unknown")
            if r.get("error"):
                lines.append(f"⚠️ {ticker}: {r['error']}")
            elif r.get("already_executed") and not is_holiday:
                target_amt = r.get("daily_target_amount", 0)
                exec_orders = r.get("executed_orders", [])
                if exec_orders:
                    lines.append(f"✅ <b>{ticker}</b>: Executed (Target ${target_amt:,.0f})")
                    for eo in exec_orders:
                        type_str = eo.get('type', 'unknown')
                        qty = eo.get('qty', 0)
                        price = eo.get('price', 0)
                        message = eo.get('message', '')
                        if type_str == 'skip':
                            lines.append(f"   └ <i>Skipped</i>")
                        elif type_str == 'buy_single_share':
                            lines.append(f"   └ Buy 1 share (${price})")
                        elif 'buy' in type_str:
                            lines.append(f"   └ Buy {qty} shares (${price})")
                        else:
                            lines.append(f"   └ {message}")
                else:
                    lines.append(f"✅ <b>{ticker}</b>: Verified (Already met)")
            else:
                day = r.get("day_count", 0)
                tgt_val = r.get("target_value_accumulated", 0)
                cur_val = r.get("current_value", 0)
                diff_pct = ((cur_val - tgt_val) / tgt_val * 100) if tgt_val > 0 else 0.0
                info_str = f"(Day {day} | Target ${tgt_val:,.0f} | Cur ${cur_val:,.0f} | {diff_pct:+.1f}%)"
                lines.append(f"⏸️ <b>{ticker}</b> {info_str}")
                lines.append(f"   └ Hold (Diff inside ±15%)")

        if is_holiday:
            lines.append("")
            lines.append("🚫 <b>휴장일 (Market Closed)</b>")

        await wrap_reply(update, "\n".join(lines), parse_mode='HTML')
        return ConversationHandler.END

    context.user_data['va_result'] = res
    context.user_data['va_pending'] = pending_results
    completed_results = [r for r in results if r not in pending_results]
    context.user_data['va_completed_results'] = completed_results
    context.user_data['va_idx'] = 0
    context.user_data['va_exec_results'] = []

    return await show_va_ticker(update, context, edit=False)


async def show_va_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = True):
    """Show the current ticker for VA confirmation."""
    pending = context.user_data.get('va_pending', [])
    idx = context.user_data.get('va_idx', 0)

    if idx >= len(pending):
        return await show_va_summary(update, context)

    result = pending[idx]
    total = len(pending)
    msg = format_va_single_ticker(result, idx, total)
    has_order = bool(result.get("orders"))
    no_order_needed = not has_order and result.get("current_price", 0) > 0
    keyboard = build_va_single_keyboard(has_order, no_order_needed)

    if edit:
        sent_msg = await wrap_edit(update, msg, parse_mode='HTML', reply_markup=keyboard)
    else:
        sent_msg = await wrap_reply(update, msg, parse_mode='HTML', reply_markup=keyboard)

    if sent_msg:
        context.user_data['va_msg_id'] = sent_msg.message_id

    return VA_CONFIRM


async def show_va_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show final summary after all tickers processed."""
    exec_results = context.user_data.get('va_exec_results', [])
    completed_results = context.user_data.get('va_completed_results', [])

    lines = ["📈 <b>Value Averaging Complete</b>", ""]

    if completed_results:
        for r in completed_results:
            ticker = r.get("target_ticker", "Unknown")
            target_amt = r.get("daily_target_amount", 0)
            lines.append(f"✅ <b>{ticker}</b>: Executed (Target: ${target_amt:,.2f})")
            exec_orders = r.get("executed_orders", [])
            for eo in exec_orders:
                type_str = eo.get('type', 'unknown')
                qty = eo.get('qty', 0)
                price = eo.get('price', 0)
                message = eo.get('message', '')
                if type_str == 'skip':
                    lines.append(f"   └ <i>Skipped</i>")
                elif 'buy' in type_str:
                    lines.append(f"   └ Buy {qty} shares (${price})")
                elif 'sell' in type_str:
                    lines.append(f"   └ Sell {qty} shares (${price})")
                else:
                    lines.append(f"   └ {message}")

    if exec_results:
        success_count = sum(1 for r in exec_results if r.get('success') and r.get('executed'))
        skip_count = sum(1 for r in exec_results if not r.get('executed'))
        for r in exec_results:
            ticker = r.get('ticker', 'Unknown')
            if r.get('executed'):
                status = "✅" if r.get('success') else "❌"
                order = r.get('order')
                target_amt = order.get('daily_target', 0) if order else 0
                lines.append(f"{status} <b>{ticker}</b>: {r.get('message', 'Unknown')} (Target: ${target_amt:,.2f})")
                if order:
                    o_type = order.get('type', 'buy')
                    qty = order.get('qty', 0)
                    price = order.get('price', 0)
                    if o_type == 'buy_single_share':
                         lines.append(f"   └ Buy 1 share (${price})")
                    else:
                         o_side = "Sell" if "sell" in o_type.lower() else "Buy"
                         lines.append(f"   └ {o_side} {qty} shares (${price})")
            else:
                lines.append(f"⏭️ <b>{ticker}</b>: Skipped (Target: ${r.get('daily_target', 0):,.2f})")
                lines.append(f"   └ Current price ${r.get('current_price', 0):,.2f}")

        lines.append("")
        total_executed = success_count + len(completed_results)
        total_skipped = skip_count
        lines.append(f"<b>Executed: {total_executed} | Skipped: {total_skipped}</b>")
    elif not completed_results:
        lines.append("<i>No actions taken.</i>")
    else:
        lines.append("")
        lines.append(f"<b>Executed: {len(completed_results)}</b>")

    await wrap_edit(update, "\n".join(lines), parse_mode='HTML')

    # Cleanup
    for key in ['va_result', 'va_pending', 'va_completed_results', 'va_idx', 'va_exec_results']:
        context.user_data.pop(key, None)

    return ConversationHandler.END


async def handle_va_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Value Averaging button clicks."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    logging.info(f"[TG] VA Callback: {callback_data}")

    pending = context.user_data.get('va_pending', [])
    idx = context.user_data.get('va_idx', 0)

    if idx >= len(pending):
        return await show_va_summary(update, context)

    current = pending[idx]
    ticker = current.get("target_ticker")
    day_count = current.get("day_count", 0)
    price = current.get("current_price", 0)
    orders = current.get("orders", [])

    loop = asyncio.get_running_loop()
    exec_results = context.user_data.get('va_exec_results', [])

    if callback_data == "va_yes":
        if orders:
            order = orders[0]
            result = await loop.run_in_executor(
                None, value_averaging.execute_single_order, ticker, order
            )
            executed = result.get('success', False)
            result['executed'] = executed
            await loop.run_in_executor(
                None, value_averaging.save_ticker_result, ticker, day_count, result, executed
            )
            exec_results.append(result)
        else:
            result = {
                "ticker": ticker, "order": None, "success": True, "message": "Skipped",
                "executed": False, "daily_target": current.get('daily_target_amount', 0),
                "current_price": price
            }
            await loop.run_in_executor(
                None, value_averaging.save_ticker_result, ticker, day_count, result, False
            )
            exec_results.append(result)
    elif callback_data == "va_no":
        result = {
            "ticker": ticker, "order": None, "success": True, "message": "Skipped",
            "executed": False, "daily_target": current.get('daily_target_amount', 0),
            "current_price": price
        }
        await loop.run_in_executor(
            None, value_averaging.save_ticker_result, ticker, day_count, result, False
        )
        exec_results.append(result)

    context.user_data['va_exec_results'] = exec_results
    context.user_data['va_idx'] = idx + 1
    return await show_va_ticker(update, context, edit=True)


async def va_timeout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle VA conversation timeout."""
    logging.info("[TG] VA session timed out")
    for key in ['va_result', 'va_pending', 'va_idx', 'va_exec_results']:
        context.user_data.pop(key, None)

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
        entry_points=[CommandHandler("value_average", cmd_value_average)],
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
    return "/value_average - Value Averaging order"
