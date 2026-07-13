# -*- coding: utf-8 -*-
"""
Telegram transport utilities.
"""
import asyncio
import logging
from typing import Callable, Optional, cast

from telegram import Bot, Message, Update
from telegram.error import NetworkError, TimedOut

MAX_RETRIES = 2
RETRY_DELAY = 1.0  # seconds

async def wrap_reply(update: Update, text: str, **kwargs):
    """
    Wrapper for update.message.reply_text that alerts the first line.
    Supports all reply_text arguments like parse_mode, reply_markup, etc.
    Retries up to MAX_RETRIES times on network timeout.
    """
    if not text: return
    first_line = text.split('\n')[0][:80]  # First line, max 80 chars
    _alert(f"[TG] {first_line}", "INFO")

    for attempt in range(MAX_RETRIES + 1):
        try:
            # Check if update.message exists (it might be a callback query)
            if update.message:
                return await update.message.reply_text(text, **kwargs)
            elif update.callback_query:
                # Fallback for callback queries if someone calls wrap_reply by mistake
                message = cast(Message, update.callback_query.message)
                return await message.reply_text(text, **kwargs)
            return None
        except (TimedOut, NetworkError) as e:
            if attempt < MAX_RETRIES:
                logging.warning(f"[TG] wrap_reply retry {attempt + 1}/{MAX_RETRIES}: {e}")
                await asyncio.sleep(RETRY_DELAY)
            else:
                _alert(f"[TG] ERR: {e}", "ERROR")
                raise

async def wrap_edit(update: Update, text: str, **kwargs):
    """
    Wrapper for query.edit_message_text that alerts the first line.
    Used for InlineKeyboard interactions.
    Retries up to MAX_RETRIES times on network timeout.
    """
    if not text: return
    first_line = text.split('\n')[0][:80]
    _alert(f"[TG] {first_line}", "INFO")

    for attempt in range(MAX_RETRIES + 1):
        try:
            if update and update.callback_query:
                return await update.callback_query.edit_message_text(text, **kwargs)
            else:
                logging.warning(f"[TG] wrap_edit failed: update={update}")
                return None
        except (TimedOut, NetworkError) as e:
            if attempt < MAX_RETRIES:
                logging.warning(f"[TG] wrap_edit retry {attempt + 1}/{MAX_RETRIES}: {e}")
                await asyncio.sleep(RETRY_DELAY)
            else:
                _alert(f"[TG] ERR: {e}", "ERROR")
                raise

# Global reference for wrap_send
_bot: Optional[Bot] = None
_chat_id: Optional[str] = None
_main_loop: Optional[asyncio.AbstractEventLoop] = None
_add_alert: Optional[Callable[[str, str], None]] = None


def _alert(message: str, level: str) -> None:
    if _add_alert is not None:
        _add_alert(message, level)


def set_telegram_bot(
    bot: Bot,
    chat_id: str,
    add_alert: Callable[[str, str], None] | None = None,
):
    """Set the global bot and chat_id for utility functions."""
    global _bot, _chat_id, _main_loop, _add_alert
    _bot = bot
    _chat_id = chat_id
    if add_alert is not None:
        _add_alert = add_alert
    try:
        _main_loop = asyncio.get_running_loop()
    except RuntimeError:
        logging.warning("[TG] set_telegram_bot called without a running loop")

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
    _alert(f"[TG] {first_line}", "INFO")

    for attempt in range(MAX_RETRIES + 1):
        try:
            return await _bot.send_message(chat_id=_chat_id, text=text, **kwargs)
        except (TimedOut, NetworkError) as e:
            if attempt < MAX_RETRIES:
                logging.warning(f"[TG] wrap_send retry {attempt + 1}/{MAX_RETRIES}: {e}")
                await asyncio.sleep(RETRY_DELAY)
            else:
                _alert(f"[TG] ERR: {e}", "ERROR")
                raise


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
    _alert(f"[TG] {first_line}", "INFO")

    for attempt in range(MAX_RETRIES + 1):
        try:
            return await _bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, **kwargs)
        except (TimedOut, NetworkError) as e:
            if attempt < MAX_RETRIES:
                logging.warning(f"[TG] wrap_edit_message retry {attempt + 1}/{MAX_RETRIES}: {e}")
                await asyncio.sleep(RETRY_DELAY)
            else:
                _alert(f"[TG] ERR: {e}", "ERROR")
                raise


def send_notification(text: str, parse_mode: str = 'HTML'):
    """
    Thread-safe synchronous notification sender.
    Can be called from any thread (e.g., WebSocket event handler).

    Args:
        text: Message text to send
        parse_mode: Parse mode for formatting ('HTML' or 'Markdown')
    """
    global _bot, _chat_id, _main_loop

    if not _bot or not _chat_id or not _main_loop:
        logging.warning("[TG] Bot/Loop not initialized for notification")
        return

    if not text:
        return

    async def _send():
        for attempt in range(MAX_RETRIES + 1):
            try:
                await _bot.send_message(
                    chat_id=_chat_id,
                    text=text,
                    parse_mode=parse_mode
                )
                first_line = text.split('\n')[0][:80]
                _alert(f"[TG] {first_line}", "INFO")
                return
            except (TimedOut, NetworkError) as e:
                if attempt < MAX_RETRIES:
                    logging.warning(f"[TG] Notification retry {attempt + 1}/{MAX_RETRIES}: {e}")
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    logging.error(f"[TG] Notification failed: {e}")
            except Exception as e:
                logging.error(f"[TG] Notification failed: {e}")
                break

    # Verify if we are in the main loop or need to schedule
    try:
        curr_loop = asyncio.get_running_loop()
        if curr_loop == _main_loop:
             # Just schedule it directly if we are already in the main loop
             asyncio.ensure_future(_send())
             return
    except RuntimeError:
        # No running loop, clearly implies we are in a non-async thread
        pass

    # Different thread or no loop -> Schedule on main loop safely
    try:
        if _main_loop and not _main_loop.is_closed():
             asyncio.run_coroutine_threadsafe(_send(), _main_loop)
        else:
             logging.error("[TG] Main loop is closed or missing, cannot send notification")
    except Exception as e:
        logging.error(f"[TG] Failed to schedule notification: {e}")
