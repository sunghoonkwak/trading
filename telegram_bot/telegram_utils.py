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


def send_notification(text: str, parse_mode: str = 'HTML'):
    """
    Thread-safe synchronous notification sender.
    Can be called from any thread (e.g., WebSocket event handler).

    Args:
        text: Message text to send
        parse_mode: Parse mode for formatting ('HTML' or 'Markdown')
    """
    global _bot, _chat_id

    if not _bot or not _chat_id:
        logging.warning("[TG] Bot not initialized for notification")
        return

    if not text:
        return

    import asyncio

    async def _send():
        try:
            await _bot.send_message(
                chat_id=_chat_id,
                text=text,
                parse_mode=parse_mode
            )
            first_line = text.split('\n')[0][:80]
            display.add_alert(f"[TG] {first_line}", "INFO")
        except Exception as e:
            logging.error(f"[TG] Notification failed: {e}")

    # Schedule the coroutine on the bot's event loop from any thread
    try:
        # Get the running loop from the bot's thread
        loop = asyncio.get_running_loop()
        asyncio.ensure_future(_send(), loop=loop)
    except RuntimeError:
        # No running event loop in current thread
        # Use run_coroutine_threadsafe if we can find the bot's loop
        try:
            # Create a new loop temporarily
            asyncio.run(_send())
        except Exception as e:
            logging.error(f"[TG] Failed to send notification: {e}")
