# -*- coding: utf-8 -*-
"""
Telegram Rebalancing Module

Handles the /rebalance command to view and execute the rebalancing strategy.
"""
import logging
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

from application.strategy_run_service import StrategyRunService
from domain.strategy.base import StrategyStatus
from interfaces.telegram.report_formatter import format_rebalancing_report

from .system import (
    clear_runtime_confirmation_pending,
    get_pending_confirmation_warning,
    mark_runtime_confirmation_pending,
)
from .utils import wrap_edit, wrap_edit_message, wrap_reply

REB_CONFIRM = 0
_strategy_run_service: StrategyRunService | None = None


def configure_strategy_run_service(service: StrategyRunService) -> None:
    """Inject the application strategy use case from the composition root."""
    global _strategy_run_service
    _strategy_run_service = service


def run_rebalancing_strategy(execute: bool = False):
    """Compatibility seam for the application rebalancing use case."""
    if _strategy_run_service is None:
        raise RuntimeError("StrategyRunService is not configured.")
    return _strategy_run_service.run_rebalancing(execute=execute)

def build_confirm_keyboard(has_orders: bool) -> Optional[InlineKeyboardMarkup]:
    if has_orders:
        keyboard = [[
            InlineKeyboardButton("✅ Execute Rebalance", callback_data="reb_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="reb_no")
        ]]
        return InlineKeyboardMarkup(keyboard)
    return None

async def cmd_rebalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /rebalance command."""
    logging.info("[TG] /rebalance from user")
    user_data = cast(dict[Any, Any], context.user_data)

    try:
        reb_rep = run_rebalancing_strategy(execute=False)
    except Exception as e:
        logging.error(f"Rebalancing Calc Error: {e}", exc_info=True)
        await wrap_reply(update, f"⚠️ Error calculating rebalancing: {e}")
        return ConversationHandler.END

    user_data['strategy_reb'] = reb_rep

    report_text = format_rebalancing_report(reb_rep)

    # Check if executable
    # Check if executable
    is_blocked = lambda r: r.get('status') in (
        StrategyStatus.HOLIDAY, StrategyStatus.DISABLED, StrategyStatus.NON_MARKET_TIME
    )

    # has_orders is true only if there are pending orders AND not blocked
    has_orders = bool(reb_rep.get('pending_orders')) and not is_blocked(reb_rep)

    keyboard = build_confirm_keyboard(has_orders)
    if has_orders:
        report_text += get_pending_confirmation_warning()
        mark_runtime_confirmation_pending(context, "rebalance")

    sent_msg = await wrap_reply(update, report_text, parse_mode='HTML', reply_markup=keyboard)
    if sent_msg:
        user_data['reb_msg_id'] = sent_msg.message_id

    return REB_CONFIRM if has_orders else ConversationHandler.END

async def handle_reb_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = cast(CallbackQuery, update.callback_query)
    user_data = cast(dict[Any, Any], context.user_data)
    await query.answer()
    data = cast(str, query.data)

    if data == "reb_no":
        await wrap_edit(update, "❌ <b>Cancelled.</b>", parse_mode='HTML')
        user_data.pop('strategy_reb', None)
        clear_runtime_confirmation_pending(context)
        return ConversationHandler.END

    if data == "reb_yes":
        await wrap_edit(update, "⏳ <b>Executing rebalance...</b>", parse_mode='HTML')

        try:
            reb_res = run_rebalancing_strategy(execute=True)
            final_report = format_rebalancing_report(reb_res)
            await wrap_edit(update, final_report, parse_mode='HTML')

        except Exception as e:
            logging.error(f"Rebalancing Exec Error: {e}", exc_info=True)
            await wrap_edit(update, f"❌ Execution Failed: {e}", parse_mode='HTML')

        user_data.pop('strategy_reb', None)
        clear_runtime_confirmation_pending(context)
        return ConversationHandler.END

async def reb_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = cast(dict[Any, Any], context.user_data)
    if 'reb_msg_id' in user_data:
        try:
            from .bot import _chat_id
            if _chat_id:
                await wrap_edit_message(
                    chat_id=_chat_id,
                    message_id=user_data['reb_msg_id'],
                    text="⏱️ <i>Session expired.</i>",
                    parse_mode='HTML'
                )
        except:
            pass
    user_data.pop('strategy_reb', None)
    clear_runtime_confirmation_pending(context)
    return ConversationHandler.END

def register_rebalancing_handlers(app: Application):
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("rebalance", cmd_rebalance)],
        states={
            REB_CONFIRM: [CallbackQueryHandler(handle_reb_callback, pattern=r'^reb_')],
            ConversationHandler.TIMEOUT: [TypeHandler(Update, reb_timeout)]
        },
        fallbacks=[],
        conversation_timeout=60
    )
    app.add_handler(conv_handler)
