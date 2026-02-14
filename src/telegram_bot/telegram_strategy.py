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
from strategy.execution_service import run_raoeo_strategy, run_va_strategy
from strategy.report_formatter import format_strategy_report
from strategy.base import StrategyOrder, OrderSide

STRATEGY_CONFIRM = 0

def build_confirm_keyboard(has_orders: bool) -> Optional[InlineKeyboardMarkup]:
    if has_orders:
        keyboard = [[
            InlineKeyboardButton("✅ Execute All", callback_data="strategy_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="strategy_no")
        ]]
        return InlineKeyboardMarkup(keyboard)
    return None

async def cmd_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /strategy command."""
    logging.info(f"[TG] /strategy from {update.effective_user.id}")
    
    try:
        raoeo_rep = run_raoeo_strategy(execute=False)
        va_rep = run_va_strategy(execute=False)
    except Exception as e:
        logging.error(f"Strategy Calc Error: {e}", exc_info=True)
        await wrap_reply(update, f"⚠️ Error calculating strategies: {e}")
        return ConversationHandler.END

    context.user_data['strategy_raoeo'] = raoeo_rep
    context.user_data['strategy_va'] = va_rep
    
    report_text = format_strategy_report(raoeo_rep, va_rep)
    
    # Check if executable (calculated and not holiday)
    is_holiday = raoeo_rep.get('status') == 'market_holiday' or va_rep.get('status') == 'market_holiday'
    has_orders = (bool(raoeo_rep.get('orders')) or bool(va_rep.get('orders'))) and not is_holiday
    
    keyboard = build_confirm_keyboard(has_orders)
    
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
        
    if data == "strategy_yes":
        await wrap_edit(update, "⏳ <b>Executing orders...</b>", parse_mode='HTML')
        
        try:
            raoeo_res = run_raoeo_strategy(execute=True)
            va_res = run_va_strategy(execute=True)
            
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
