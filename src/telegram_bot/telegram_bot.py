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

from .telegram_strategy import register_strategy_handlers
from .telegram_rebalancing import register_rebalancing_handlers
from .telegram_portfolio import register_portfolio_handlers, get_portfolio_commands_desc
from .telegram_memo import register_memo_handler, get_memo_commands_desc
from .telegram_utils import wrap_send, set_telegram_bot, wrap_reply
from core import display

import uuid

# Module state
_app: Optional[Application] = None
_bot_token: Optional[str] = None
_chat_id: Optional[str] = None
_session_id: str = str(uuid.uuid4())[:8]  # Unique session ID (first 8 chars)
_init_lock = threading.Lock()
_is_initialized = False


def load_telegram_credentials() -> tuple[Optional[str], Optional[str]]:
    """Load Telegram bot token and chat ID."""
    try:
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
    """Command handler for /daily_report [YYYYMMDD]"""
    logging.info(f"[TG] /daily_report from user")
    args = context.args
    target_date = ""

    if args:
        target_date = args[0].replace("-", "")
    else:
        try:
            from scheduler.scheduler_portfolio import REPORTS_DIR
            import glob
            list_of_files = glob.glob(os.path.join(REPORTS_DIR, "report_*.txt"))
            if list_of_files:
                latest_file = max(list_of_files, key=os.path.getctime)
                target_date = os.path.basename(latest_file).replace("report_", "").replace(".txt", "")
        except Exception as e:
            logging.error(f"[TG] Failed to find latest report: {e}")

    if not target_date:
        await wrap_reply(update, "⚠️ No reports found or invalid date.", parse_mode='HTML')
        return

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
    Uses asyncio event loop explicitly to avoid set_wakeup_fd issues.
    """
    global _app, _bot_token, _chat_id, _is_initialized

    with _init_lock:
        if _is_initialized:
            logging.warning(f"[Telegram] Bot initialization skipped (already initialized in Session {_session_id})")
            return True
        _is_initialized = True

    logging.info(f"[Telegram] Initializing bot... (Session: {_session_id})")

    _bot_token, _chat_id = load_telegram_credentials()
    if not _bot_token or not _chat_id:
        logging.error("Failed to load Telegram credentials. Bot not started.")
        return False

    def run_bot():
        """Run bot with explicit loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def main():
            global _app

            # Async Error Handler
            async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
                if context.error is None: return
                from telegram.error import BadRequest
                if isinstance(context.error, BadRequest) and "Message is not modified" in str(context.error):
                    return
                display.add_alert(f"[TG] ERR: {str(context.error)[:100]}", "ERROR")
                logging.error(f"Telegram Exception: {context.error}", exc_info=context.error)

            # Build Application
            _app = Application.builder().token(_bot_token).build()

            # Register Handlers
            set_telegram_bot(_app.bot, _chat_id)
            register_portfolio_handlers(_app)
            register_strategy_handlers(_app)
            register_rebalancing_handlers(_app)
            register_memo_handler(_app)
            _app.add_handler(CommandHandler("daily_report", cmd_daily_report))
            _app.add_error_handler(error_handler)

            # Init & Start
            await _app.initialize()
            await _app.start()

            # Send Init Message
            try:
                port_desc = get_portfolio_commands_desc().strip()
                memo_desc = get_memo_commands_desc().strip()
                init_text = (
                    f"🤖 <b>Trading Bot Initialized</b> (Session: <code>{_session_id}</code>)\n\n"
                    "Commands:\n"
                    f"{port_desc}\n\n"
                    "/strategy - RAOEO & VA Strategies\n"
                    "/rebalance - TQQQ+SCHD Rebalancing\n\n"
                    "/daily_report [date] - View past reports\n"
                    f"{memo_desc}"
                )
                await wrap_send(init_text, parse_mode='HTML')
            except Exception as e:
                logging.error(f"[TG] Init send failed: {e}")

            # Polling
            logging.info("[Telegram] Starting polling...")
            await _app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )

            # Wait forever
            await asyncio.Event().wait()

        try:
            loop.run_until_complete(main())
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
        requests.post(url, data=params, timeout=5)
    except Exception as e:
        logging.error(f"[Telegram] Failed to send shutdown message: {e}")
