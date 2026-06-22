# -*- coding: utf-8 -*-
"""
Telegram Strategy Module (Refactored)

Handles the /strategy command to view and execute all active strategies.
"""
import logging
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    ConversationHandler, CallbackQueryHandler, TypeHandler
)
from .telegram_utils import wrap_reply, wrap_edit, wrap_edit_message
from strategy.execution_service import (
    TZ_ET,
    execute_raoeo_cash_funding,
    prepare_raoeo_cash_funding,
    run_strategy_suite,
    save_raoeo_cash_funding_result,
)
from strategy.report_formatter import format_strategy_report
from strategy.base import StrategyOrder, StrategyStatus, OrderSide
from datetime import datetime

STRATEGY_CONFIRM = 0

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
    logging.info(f"[TG] /strategy from user")

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

    context.user_data['strategy_raoeo'] = raoeo_rep
    context.user_data['strategy_va'] = va_rep

    report_text = format_strategy_report(raoeo_rep, va_rep)
    keyboard = build_confirm_keyboard(has_orders, cash_funding_required)

    sent_msg = await wrap_reply(update, report_text, parse_mode='HTML', reply_markup=keyboard)
    if sent_msg:
        context.user_data['strategy_msg_id'] = sent_msg.message_id

    return STRATEGY_CONFIRM if has_orders else ConversationHandler.END

async def handle_strategy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "strategy_no":
        await wrap_edit(update, "❌ <b>Cancelled.</b>", parse_mode='HTML')
        context.user_data.pop('strategy_raoeo', None)
        context.user_data.pop('strategy_va', None)
        return ConversationHandler.END

    if data in ("strategy_with_cash_sale", "strategy_without_cash_sale"):
        await wrap_edit(update, "⏳ <b>Executing orders...</b>", parse_mode='HTML')

        try:
            funding_result = None
            if data == "strategy_with_cash_sale":
                stored_raoeo_report = context.user_data.get('strategy_raoeo')
                funding_result, funding_info = execute_raoeo_cash_funding(
                    stored_raoeo_report
                )
                funding_failed = (
                    funding_info.get("required")
                    and (funding_result is None or not funding_result["success"])
                )
                if funding_result is not None:
                    report_date = context.user_data.get(
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
                    context.user_data.pop('strategy_raoeo', None)
                    context.user_data.pop('strategy_va', None)
                    return ConversationHandler.END

            raoeo_res, va_res = run_strategy_suite(execute=True)
            if funding_result is not None:
                raoeo_res["cash_funding_results"] = [funding_result]

            final_report = format_strategy_report(raoeo_res, va_res)
            await wrap_edit(update, final_report, parse_mode='HTML')

        except Exception as e:
            logging.error(f"Strategy Exec Error: {e}", exc_info=True)
            await wrap_edit(update, f"❌ Execution Failed: {e}", parse_mode='HTML')

        context.user_data.pop('strategy_raoeo', None)
        context.user_data.pop('strategy_va', None)
        return ConversationHandler.END

async def strategy_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'strategy_msg_id' in context.user_data:
        try:
            from .telegram_bot import _chat_id
            if _chat_id:
                await wrap_edit_message(
                    chat_id=_chat_id,
                    message_id=context.user_data['strategy_msg_id'],
                    text="⏱️ <i>Session expired.</i>",
                    parse_mode='HTML'
                )
        except:
            pass
    context.user_data.pop('strategy_raoeo', None)
    context.user_data.pop('strategy_va', None)
    return ConversationHandler.END

def register_strategy_handlers(app: Application):
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("strategy", cmd_strategy)],
        states={
            STRATEGY_CONFIRM: [CallbackQueryHandler(handle_strategy_callback, pattern=r'^strategy_')],
            ConversationHandler.TIMEOUT: [TypeHandler(object, strategy_timeout)]
        },
        fallbacks=[],
        conversation_timeout=60
    )
    app.add_handler(conv_handler)
