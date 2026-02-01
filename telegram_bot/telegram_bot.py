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
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .telegram_raoeo import register_raoeo_handlers, get_raoeo_commands_desc
from .telegram_portfolio import register_portfolio_handlers, get_portfolio_commands_desc
from .telegram_memo import register_memo_handler, get_memo_commands_desc
from .telegram_utils import wrap_send, set_telegram_bot
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
        # Load telegram credentials file from KIS_config directory
        config_root = os.path.join(os.path.expanduser("~"), "KIS_config")
        telegram_file_info = os.path.join(config_root, "telegram.txt")
        if not os.path.exists(telegram_file_info):
            logging.error(f"telegram.txt not found at {telegram_file_info}")
            return None, None

        with open(telegram_file_info, "r") as file:
            bot_token, chat_id = file.read().split(',')[:2]
        return bot_token.strip(), chat_id.strip()

    except Exception as e:
        logging.error(f"Error loading Telegram credentials: {e}")
        return None, None


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

            # Pass bot instance to utils
            set_telegram_bot(_app.bot, _chat_id)

            # Register strategy handlers
            register_raoeo_handlers(_app)
            register_portfolio_handlers(_app)
            register_memo_handler(_app)  # Saves arbitrary text messages

            # Send initialization message
            async def send_init_message():
                raoeo_desc = get_raoeo_commands_desc()
                port_desc = get_portfolio_commands_desc()
                memo_desc = get_memo_commands_desc()
                init_text = (
                    "🤖 <b>Trading Bot Initialized</b>\n\n"
                    "Commands:\n"
                    f"{raoeo_desc}\n"
                    f"{port_desc}\n"
                    f"{memo_desc}"
                )
                try:
                    await wrap_send(init_text, parse_mode='HTML')
                except Exception as e:
                    logging.error(f"[Telegram] Failed to send init message: {e}")
                    # Fallback to plain text
                    try:
                        fallback_text = f"🤖 Trading Bot Initialized\n\nCommands:\n/raoeo_report\n/raoeo_order"
                        await wrap_send(fallback_text)
                    except Exception as e2:
                        logging.error(f"[Telegram] Fallback also failed: {e2}")
                        display.add_alert("[TG] Init message failed", "ERROR")

            # Global Error Handler (Essential for stability)
            # Global Error Handler (Essential for stability)
            from telegram.error import BadRequest

            async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
                # Ignore if no error present
                if context.error is None:
                    return

                # Filter out benign "Message is not modified" error
                if isinstance(context.error, BadRequest) and "Message is not modified" in str(context.error):
                    logging.warning(f"[TG] Benign error (ignored): {context.error}")
                    return

                # Increase alert length to 100 chars
                display.add_alert(f"[TG] ERR: {str(context.error)[:100]}", "ERROR")
                logging.error(f"Telegram Exception: {context.error}", exc_info=context.error)

            _app.add_error_handler(error_handler)

            loop.run_until_complete(_app.initialize())
            loop.run_until_complete(_app.start())
            loop.run_until_complete(_app.updater.start_polling(allowed_updates=Update.ALL_TYPES))
            loop.run_until_complete(send_init_message())

            loop.run_forever()

        except Exception as e:
            display.add_alert(f"[TG] CRITICAL ERROR: {str(e)[:40]}", "ERROR")
            logging.error(f"Telegram bot error: {e}")
        finally:
            loop.close()

    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    return True

def shutdown_telegram(message: str = "🛑 <b>Trading Bot Stopped</b>"):
    """
    Send a final message to Telegram before the program exits.
    Uses direct API call for simplicity during shutdown.
    """
    global _bot_token, _chat_id
    if not _bot_token or not _chat_id:
        return

    try:
        url = f"https://api.telegram.org/bot{_bot_token}/sendMessage"
        params = {
            "chat_id": _chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        # Use a short timeout to prevent hanging the exit process
        requests.post(url, data=params, timeout=5)
    except Exception as e:
        logging.error(f"[Telegram] Failed to send shutdown message: {e}")
