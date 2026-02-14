# -*- coding: utf-8 -*-
"""
Telegram Rebalancing Module

Handles the /rebalance command to view and execute the rebalancing strategy.
"""
import logging
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    ConversationHandler, CallbackQueryHandler, TypeHandler
)
from .telegram_utils import wrap_reply, wrap_edit, wrap_edit_message
from strategy.execution_service import run_rebalancing_strategy
from strategy.report_formatter import format_rebalancing_report

REB_CONFIRM = 0

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
    logging.info(f"[TG] /rebalance from {update.effective_user.id}")
    
    try:
        reb_rep = run_rebalancing_strategy(execute=False)
    except Exception as e:
        logging.error(f"Rebalancing Calc Error: {e}", exc_info=True)
        await wrap_reply(update, f"⚠️ Error calculating rebalancing: {e}")
        return ConversationHandler.END

    context.user_data['strategy_reb'] = reb_rep
    
    report_text = format_rebalancing_report(reb_rep)
    
    # Check if executable
    is_holiday = reb_rep.get('status') == 'market_holiday'
    has_orders = bool(reb_rep.get('orders')) and not is_holiday
    
    keyboard = build_confirm_keyboard(has_orders)
    
    sent_msg = await wrap_reply(update, report_text, parse_mode='HTML', reply_markup=keyboard)
    if sent_msg:
        context.user_data['reb_msg_id'] = sent_msg.message_id
        
    return REB_CONFIRM if has_orders else ConversationHandler.END

async def handle_reb_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "reb_no":
        await wrap_edit(update, "❌ <b>Cancelled.</b>", parse_mode='HTML')
        context.user_data.pop('strategy_reb', None)
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
            
        context.user_data.pop('strategy_reb', None)
        return ConversationHandler.END

async def reb_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'reb_msg_id' in context.user_data:
        try:
            from .telegram_bot import _chat_id
            if _chat_id:
                await wrap_edit_message(
                    chat_id=_chat_id,
                    message_id=context.user_data['reb_msg_id'],
                    text="⏱️ <i>Session expired.</i>",
                    parse_mode='HTML'
                )
        except:
            pass
    context.user_data.pop('strategy_reb', None)
    return ConversationHandler.END

def register_rebalancing_handlers(app: Application):
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("rebalance", cmd_rebalance)],
        states={
            REB_CONFIRM: [CallbackQueryHandler(handle_reb_callback, pattern=r'^reb_')],
            ConversationHandler.TIMEOUT: [TypeHandler(object, reb_timeout)]
        },
        fallbacks=[],
        conversation_timeout=60
    )
    app.add_handler(conv_handler)
