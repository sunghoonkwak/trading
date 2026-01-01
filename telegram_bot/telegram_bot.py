# -*- coding: utf-8 -*-
"""
Telegram Integration Module

This module provides Telegram bot functionality for remote access to
trading commands and notifications.
"""
import os
import logging
import asyncio
import threading
from typing import Optional

# Telegram imports
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .telegram_raoeo import register_raoeo_handlers, get_raoeo_commands_desc
import display

# Module state
_app: Optional[Application] = None
_bot_token: Optional[str] = None
_chat_id: Optional[str] = None


def load_telegram_credentials() -> tuple[Optional[str], Optional[str]]:
    """
    Load Telegram bot token and chat ID from credentials.enc.

    Returns:
        tuple[str, str]: (bot_token, chat_id)
    """
    try:
        # Load telegram credentials file
        telegram_file_info = os.path.join(os.path.dirname(__file__), "telegram.txt")
        if not os.path.exists(telegram_file_info):
            logging.error("telegram.txt not found")
            return None, None

        with open(telegram_file_info, "r") as file:
            bot_token, chat_id = file.read().split(',')[:2]
        return bot_token.strip(), chat_id.strip()

    except Exception as e:
        logging.error(f"Error loading Telegram credentials: {e}")
        return None, None


async def wrap_reply(update: Update, text: str, parse_mode: str = None):
    """
    Wrapper for update.message.reply_text that logs and alerts the first line.

    Args:
        update: Telegram Update object
        text: Message text to send
        parse_mode: Optional parse mode ('Markdown', 'MarkdownV2', 'HTML')
    """
    first_line = text.split('\n')[0][:50]  # First line, max 50 chars
    display.queue_alert(f"[TG] {first_line}", "INFO")
    await update.message.reply_text(text, parse_mode=parse_mode)


async def wrap_send(text: str, parse_mode: str = None):
    """
    Wrapper for bot.send_message that logs and alerts the first line.

    Args:
        text: Message text to send
        parse_mode: Optional parse mode ('Markdown', 'MarkdownV2', 'HTML')
    """
    global _app, _chat_id

    if not _app or not _chat_id:
        logging.warning("[TG] Bot not initialized for send_message")
        return

    first_line = text.split('\n')[0][:50]  # First line, max 50 chars
    display.queue_alert(f"[TG] {first_line}", "INFO")
    await _app.bot.send_message(chat_id=_chat_id, text=text, parse_mode=parse_mode)


def initialize_telegram():
    """
    Initialize Telegram bot and start polling in a background thread.
    Sends 'initialized' message upon successful startup.
    """
    global _app, _bot_token, _chat_id

    logging.info("[Telegram] Initializing bot...")

    # Load credentials
    _bot_token, _chat_id = load_telegram_credentials()
    if not _bot_token or not _chat_id:
        logging.error("Failed to load Telegram credentials. Bot not started.")
        return False

    def run_bot():
        """Run bot in separate thread with its own event loop."""
        global _app

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            _app = Application.builder().token(_bot_token).build()

            # Register strategy handlers
            register_raoeo_handlers(_app)

            # Send initialization message
            async def send_init_message():
                raoeo_desc = get_raoeo_commands_desc()
                init_text = (
                    "🤖 *Trading Bot Initialized*\n\n"
                    "Commands:\n"
                    f"{raoeo_desc}"
                )
                try:
                    await wrap_send(init_text, parse_mode='MarkdownV2')
                except Exception as e:
                    logging.error(f"[Telegram] Failed to send init message: {e}")
                    # Fallback to plain text
                    try:
                        fallback_text = f"🤖 Trading Bot Initialized\n\nCommands:\n/raoeo_report\n/raoeo_order"
                        await wrap_send(fallback_text)
                    except Exception as e2:
                        logging.error(f"[Telegram] Fallback also failed: {e2}")
                        display.queue_alert("[TG] Init message failed", "ERROR")

            loop.run_until_complete(_app.initialize())
            loop.run_until_complete(send_init_message())

            logging.info("[Telegram] Bot initialized and running")

            # Run polling (blocking)
            loop.run_until_complete(_app.updater.start_polling(allowed_updates=Update.ALL_TYPES))
            loop.run_until_complete(_app.start())
            loop.run_forever()

        except Exception as e:
            logging.error(f"Telegram bot error: {e}")
        finally:
            loop.close()

    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    return True

