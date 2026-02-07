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
from .telegram_va import register_va_handlers, get_va_commands_desc
from .telegram_memo import register_memo_handler, get_memo_commands_desc
from .telegram_utils import wrap_send, set_telegram_bot, wrap_reply
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



async def cmd_daily_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Command handler for /daily_report [YYYYMMDD]
    Retrieves and displays a past portfolio report.
    """
    args = context.args
    target_date = ""

    # Determine target date
    if args:
        target_date = args[0].replace("-", "")  # Allow 2024-02-01 format
    else:
        # Default to latest report
        try:
            from scheduler.scheduler_portfolio import REPORTS_DIR
            import glob
            list_of_files = glob.glob(os.path.join(REPORTS_DIR, "report_*.txt"))
            if list_of_files:
                latest_file = max(list_of_files, key=os.path.getctime)
                # Extract date from filename: report_YYYYMMDD.txt
                base = os.path.basename(latest_file)
                target_date = base.replace("report_", "").replace(".txt", "")
        except Exception as e:
            logging.error(f"[TG] Failed to find latest report: {e}")

    if not target_date:
        await wrap_reply(update, "⚠️ No reports found or invalid date.", parse_mode='HTML')
        return

    # Read Report
    try:
        from scheduler.scheduler_portfolio import REPORTS_DIR
        report_path = os.path.join(REPORTS_DIR, f"report_{target_date}.txt")

        if not os.path.exists(report_path):
             await wrap_reply(update, f"⚠️ Report not found for {target_date}", parse_mode='HTML')
             return

        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()

        header = f"📄 <b>Daily Report Archive ({target_date})</b>\n\n"
        await wrap_reply(update, header + content, parse_mode='HTML')

    except Exception as e:
        await wrap_reply(update, f"⚠️ Error reading report: {e}", parse_mode='HTML')


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

        async def main():
            global _app
            _app = Application.builder().token(_bot_token).build()

            # Pass bot instance to utils
            set_telegram_bot(_app.bot, _chat_id)

            # Register strategy handlers
            register_portfolio_handlers(_app)
            register_raoeo_handlers(_app)
            register_va_handlers(_app)
            register_memo_handler(_app)  # Saves arbitrary text messages

            # Register Global Commands
            _app.add_handler(CommandHandler("daily_report", cmd_daily_report))

            # Global Error Handler
            from telegram.error import BadRequest
            async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
                if context.error is None: return
                if isinstance(context.error, BadRequest) and "Message is not modified" in str(context.error):
                    logging.warning(f"[TG] Benign error (ignored): {context.error}")
                    return
                display.add_alert(f"[TG] ERR: {str(context.error)[:100]}", "ERROR")
                logging.error(f"Telegram Exception: {context.error}", exc_info=context.error)

            _app.add_error_handler(error_handler)

            # Send initialization message
            raoeo_desc = get_raoeo_commands_desc().strip()
            port_desc = get_portfolio_commands_desc().strip()
            va_desc = get_va_commands_desc().strip()
            memo_desc = get_memo_commands_desc().strip()
            init_text = (
                "🤖 <b>Trading Bot Initialized</b>\n\n"
                "Commands:\n"
                f"{port_desc}\n\n"
                f"{raoeo_desc}\n"
                f"{va_desc}\n\n"
                "/daily_report [date] - View past reports\n"
                f"{memo_desc}"
            )

            # Initialize and start application
            await _app.initialize()
            await _app.start()

            try:
                # Send init message safely after start
                await wrap_send(init_text, parse_mode='HTML')
            except Exception as e:
                logging.error(f"[TG] Init send failed: {e}")

            # Run polling endlessly
            await _app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

            # Keep the app running
            # In v20+, start_polling starts the updater but we need to keep the script alive.
            # But here we are in a thread.
            # Note: app.run_polling() is the blocking helper, but we are doing components manually.
            # Let's just use run_polling()! It handles everything including init, start, updater, and blocking.
            # Re-building app to strictly follow run_polling pattern if possible,
            # BUT we need to register handlers first.
            await asyncio.Event().wait() # Wait forever

        try:
            # Use asyncio.run for robust loop management in this thread
            asyncio.run(main())
        except Exception as e:
            display.add_alert(f"[TG] CRITICAL ERROR: {str(e)[:40]}", "ERROR")
            logging.error(f"Telegram bot error: {e}")

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
