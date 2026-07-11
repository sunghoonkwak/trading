# -*- coding: utf-8 -*-
"""
Telegram Strategy Module (Refactored)

Handles the /strategy command to view and execute all active strategies.
"""
import logging
from datetime import datetime
from html import escape
from typing import Any, Optional, cast

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    TypeHandler,
)

from interfaces.telegram.report_formatter import format_strategy_report
from domain.strategy.base import StrategyStatus
from strategy.constants import TZ_ET
from strategy.execution_service import (
    clear_strategy_history_for_date,
    execute_raoeo_cash_funding,
    get_strategy_run_service,
    normalize_strategy_history_date,
    prepare_raoeo_cash_funding,
    save_raoeo_cash_funding_result,
)
from telegram_bot.telegram_system import (
    clear_runtime_confirmation_pending,
    get_pending_confirmation_warning,
    mark_runtime_confirmation_pending,
)
from telegram_bot.telegram_utils import wrap_edit, wrap_edit_message, wrap_reply

STRATEGY_CONFIRM = 0


def run_strategy_suite(execute: bool = False):
    """Compatibility seam for the shared application strategy use case."""
    return get_strategy_run_service().run_suite(execute=execute)

def build_confirm_keyboard(
    has_orders: bool,
    cash_funding_required: bool = False,
) -> Optional[InlineKeyboardMarkup]:
    if not has_orders:
        return None

    keyboard = []
    if cash_funding_required:
        keyboard.append([
            InlineKeyboardButton(
                "💵 Sell cash_ticker & Execute",
                callback_data="strategy_with_cash_sale",
            )
        ])
    keyboard.append([
        InlineKeyboardButton(
            "✅ Execute Without Cash Sale",
            callback_data="strategy_without_cash_sale",
        )
    ])
    keyboard.append([
        InlineKeyboardButton("❌ Cancel", callback_data="strategy_no")
    ])
    return InlineKeyboardMarkup(keyboard)

async def cmd_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /strategy command."""
    logging.info("[TG] /strategy from user")
    user_data = cast(dict[Any, Any], context.user_data)

    try:
        raoeo_rep, va_rep = run_strategy_suite(execute=False)
    except Exception as e:
        logging.error(f"Strategy Calc Error: {e}", exc_info=True)
        await wrap_reply(update, f"⚠️ Error calculating strategies: {e}")
        return ConversationHandler.END

    # Check if executable
    is_blocked = lambda r: r.get('status') in (
        StrategyStatus.HOLIDAY, StrategyStatus.DISABLED, StrategyStatus.NON_MARKET_TIME
    )

    raoeo_has_orders = bool(raoeo_rep.get('pending_orders')) and not is_blocked(raoeo_rep)
    va_has_orders = bool(va_rep.get('pending_orders')) and not is_blocked(va_rep)

    has_orders = raoeo_has_orders or va_has_orders
    cash_funding_required = False
    if raoeo_has_orders:
        try:
            funding_order, funding_info = prepare_raoeo_cash_funding(raoeo_rep)
            raoeo_rep["cash_funding"] = {
                **funding_info,
                "order": funding_order,
            }
            cash_funding_required = bool(funding_info.get("required"))
        except Exception as e:
            logging.error(f"Cash Funding Calculation Error: {e}", exc_info=True)
            await wrap_reply(update, f"⚠️ Error calculating cash funding: {e}")
            return ConversationHandler.END

    user_data['strategy_raoeo'] = raoeo_rep
    user_data['strategy_va'] = va_rep

    report_text = format_strategy_report(raoeo_rep, va_rep)
    keyboard = build_confirm_keyboard(has_orders, cash_funding_required)
    if has_orders:
        report_text += get_pending_confirmation_warning()
        mark_runtime_confirmation_pending(context, "strategy")

    sent_msg = await wrap_reply(update, report_text, parse_mode='HTML', reply_markup=keyboard)
    if sent_msg:
        user_data['strategy_msg_id'] = sent_msg.message_id

    return STRATEGY_CONFIRM if has_orders else ConversationHandler.END


async def cmd_clear_strategy_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_date = context.args[0] if context.args else ""
    try:
        target_date = normalize_strategy_history_date(raw_date)
    except ValueError as e:
        escaped_date = escape(raw_date)
        await wrap_reply(
            update,
            f"⚠️ Invalid date: <code>{escaped_date}</code>\n"
            f"{escape(str(e))}",
            parse_mode='HTML',
        )
        return
    logging.info("[TG] /clear_strategy_history date=%s", target_date)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🧹 Clear Strategy History",
                callback_data=f"clear_strategy_history_yes:{target_date}",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="clear_strategy_history_no",
            )
        ],
    ])
    await wrap_reply(
        update,
        f"⚠️ Clear all strategy history for <b>{target_date}</b>?\n"
        "This deletes RAOEO, VA, and rebalancing history for that date so they can run again."
        f"{get_pending_confirmation_warning()}",
        parse_mode='HTML',
        reply_markup=keyboard,
    )
    mark_runtime_confirmation_pending(context, "clear_strategy_history")


async def handle_clear_strategy_history_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = cast(CallbackQuery, update.callback_query)
    await query.answer()
    data = cast(str, query.data)

    if data == "clear_strategy_history_no":
        await wrap_edit(update, "❌ <b>Cancelled.</b>", parse_mode='HTML')
        clear_runtime_confirmation_pending(context)
        return

    if not data.startswith("clear_strategy_history_yes:"):
        return

    target_date = data.split(":", 1)[1]
    try:
        result = clear_strategy_history_for_date(target_date)
        if result["removed"]:
            message = f"✅ Cleared all strategy history for {result['date']}."
        else:
            message = f"ℹ️ No strategy history found for {result['date']}."
        await wrap_edit(update, message, parse_mode='HTML')
    except Exception as e:
        logging.error("[TG] clear strategy history failed: %s", e, exc_info=True)
        await wrap_edit(
            update,
            f"❌ <b>Failed to clear strategy history.</b>\n{e}",
            parse_mode='HTML',
        )
    finally:
        clear_runtime_confirmation_pending(context)

async def handle_strategy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = cast(CallbackQuery, update.callback_query)
    user_data = cast(dict[Any, Any], context.user_data)
    await query.answer()
    data = cast(str, query.data)

    if data == "strategy_no":
        await wrap_edit(update, "❌ <b>Cancelled.</b>", parse_mode='HTML')
        user_data.pop('strategy_raoeo', None)
        user_data.pop('strategy_va', None)
        clear_runtime_confirmation_pending(context)
        return ConversationHandler.END

    if data in ("strategy_with_cash_sale", "strategy_without_cash_sale"):
        await wrap_edit(update, "⏳ <b>Executing orders...</b>", parse_mode='HTML')

        try:
            funding_result = None
            if data == "strategy_with_cash_sale":
                stored_raoeo_report = user_data.get('strategy_raoeo')
                funding_result, funding_info = execute_raoeo_cash_funding(
                    stored_raoeo_report
                )
                funding_failed = (
                    funding_info.get("required")
                    and (funding_result is None or not funding_result["success"])
                )
                if funding_result is not None:
                    report_date = user_data.get(
                        'strategy_raoeo', {}
                    ).get('date', datetime.now(TZ_ET).strftime("%Y-%m-%d"))
                    save_raoeo_cash_funding_result(report_date, funding_result)
                if funding_failed:
                    reason = funding_info.get("error")
                    if funding_result is not None:
                        reason = funding_result.get("message")
                    await wrap_edit(
                        update,
                        f"❌ <b>Cash funding failed.</b>\n{reason or 'Funding sale unavailable.'}",
                        parse_mode='HTML',
                    )
                    user_data.pop('strategy_raoeo', None)
                    user_data.pop('strategy_va', None)
                    clear_runtime_confirmation_pending(context)
                    return ConversationHandler.END

            raoeo_res, va_res = run_strategy_suite(execute=True)
            if funding_result is not None:
                raoeo_res["cash_funding_results"] = [funding_result]

            final_report = format_strategy_report(raoeo_res, va_res)
            await wrap_edit(update, final_report, parse_mode='HTML')

        except Exception as e:
            logging.error(f"Strategy Exec Error: {e}", exc_info=True)
            await wrap_edit(update, f"❌ Execution Failed: {e}", parse_mode='HTML')

        user_data.pop('strategy_raoeo', None)
        user_data.pop('strategy_va', None)
        clear_runtime_confirmation_pending(context)
        return ConversationHandler.END

async def strategy_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = cast(dict[Any, Any], context.user_data)
    if 'strategy_msg_id' in user_data:
        try:
            from telegram_bot.telegram_bot import _chat_id
            if _chat_id:
                await wrap_edit_message(
                    chat_id=_chat_id,
                    message_id=user_data['strategy_msg_id'],
                    text="⏱️ <i>Session expired.</i>",
                    parse_mode='HTML'
                )
        except:
            pass
    user_data.pop('strategy_raoeo', None)
    user_data.pop('strategy_va', None)
    clear_runtime_confirmation_pending(context)
    return ConversationHandler.END

def register_strategy_handlers(app: Application):
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("strategy", cmd_strategy)],
        states={
            STRATEGY_CONFIRM: [CallbackQueryHandler(handle_strategy_callback, pattern=r'^strategy_')],
            ConversationHandler.TIMEOUT: [TypeHandler(Update, strategy_timeout)]
        },
        fallbacks=[],
        conversation_timeout=60
    )
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("clear_strategy_history", cmd_clear_strategy_history))
    app.add_handler(CallbackQueryHandler(
        handle_clear_strategy_history_callback,
        pattern=r'^clear_strategy_history_',
    ))
