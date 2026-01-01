# -*- coding: utf-8 -*-
"""
Telegram Utilities
"""
import logging
from telegram import Update
import display

async def wrap_reply(update: Update, text: str, **kwargs):
    """
    Wrapper for update.message.reply_text that alerts the first line.
    Supports all reply_text arguments like parse_mode, reply_markup, etc.
    """
    if not text: return
    first_line = text.split('\n')[0][:80]  # First line, max 80 chars
    display.add_alert(f"[TG] {first_line}", "INFO")

    # Check if update.message exists (it might be a callback query)
    if update.message:
        return await update.message.reply_text(text, **kwargs)
    elif update.callback_query:
        # Fallback for callback queries if someone calls wrap_reply by mistake
        return await update.callback_query.message.reply_text(text, **kwargs)
    return None

async def wrap_edit(update: Update, text: str, **kwargs):
    """
    Wrapper for query.edit_message_text that alerts the first line.
    Used for InlineKeyboard interactions.
    """
    if not text: return
    first_line = text.split('\n')[0][:80]
    display.add_alert(f"[TG] {first_line}", "INFO")

    if update and update.callback_query:
        return await update.callback_query.edit_message_text(text, **kwargs)
    else:
        logging.warning(f"[TG] wrap_edit failed: update={update}")
        return None

# Global reference for wrap_send
from telegram import Bot
_bot: Bot = None
_chat_id: str = None

def set_telegram_bot(bot: Bot, chat_id: str):
    """Set the global bot and chat_id for utility functions."""
    global _bot, _chat_id
    _bot = bot
    _chat_id = chat_id

async def wrap_send(text: str, **kwargs):
    """
    Wrapper for bot.send_message that alerts the first line.
    Uses globally set bot and chat_id.
    """
    global _bot, _chat_id

    if not _bot or not _chat_id:
        logging.warning("[TG] Bot not initialized for send_message")
        return

    if not text: return
    first_line = text.split('\n')[0][:80]
    display.add_alert(f"[TG] {first_line}", "INFO")
    return await _bot.send_message(chat_id=_chat_id, text=text, **kwargs)


async def wrap_edit_message(chat_id: str, message_id: int, text: str, **kwargs):
    """
    Wrapper for bot.edit_message_text that alerts the first line.
    Uses globally set bot.
    """
    global _bot

    if not _bot:
        logging.warning("[TG] Bot not initialized for edit_message_text")
        return

    if not text: return
    first_line = text.split('\n')[0][:80]
    display.add_alert(f"[TG] {first_line}", "INFO")
    return await _bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, **kwargs)
