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

from menu.raoeo.raoeo import build_raoeo_report, execute_orders, save_history
import display

# Module state
_app: Optional[Application] = None
_bot_token: Optional[str] = None
_chat_id: Optional[str] = None
_cached_result: Optional[dict] = None  # Stores current_result from last report


def load_telegram_credentials() -> tuple[str, str]:
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


def format_raoeo_report(report: dict) -> str:
    """
    Format RAOEO report for Telegram message.

    Args:
        report: Result from build_raoeo_report()

    Returns:
        str: Formatted message for Telegram
    """
    lines = []

    if report.get("executed_today"):
        entry = report["executed_today"]
        lines.append(f"📊 *RAOEO Executed - {entry['date']}*")
        lines.append(f"Target: `{entry['config']['target']}` @ {entry['config']['exchange']}")
        lines.append(f"Holdings: {entry['holdings']['qty']} shares @ ${entry['holdings']['avg_price']:.2f}")
        lines.append("")
        lines.append("✅ *Executed Orders:*")
        for i, order in enumerate(entry['orders'], 1):
            emoji = "🟢" if order['type'].lower() == 'buy' else "🔴"
            lines.append(f"  {emoji} {order['type'].upper()} {order['qty']} @ ${order['price']:.2f}")

    elif report.get("error") and not report.get("current_result"):
        lines.append(f"⚠️ *Error:* {report['error']}")

    elif report.get("current_result"):
        result = report["current_result"]
        if result.get('error'):
            lines.append(f"⚠️ *Error:* {result['error']}")
        elif not result.get('orders'):
            lines.append(f"📊 *RAOEO - {result['date']}*")
            lines.append("No orders calculated for today.")
        else:
            lines.append(f"📊 *RAOEO Order Calculation - {result['date']}*")
            lines.append(f"Target: `{result['config']['target']}` @ {result['config']['exchange']}")
            lines.append(f"Current Price: ${result['holdings']['cur_price']:.2f}")
            lines.append(f"Holdings: {result['holdings']['qty']} @ ${result['holdings']['avg_price']:.2f}")
            lines.append("")
            lines.append("📋 *Pending Orders:*")
            for i, order in enumerate(result['orders'], 1):
                emoji = "🟢" if order['type'].lower() == 'buy' else "🔴"
                lines.append(f"  {emoji} {order['type'].upper()} {order['qty']} @ ${order['price']:.2f}")
                lines.append(f"      _{order['desc']}_")

    return "\n".join(lines)


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


async def cmd_raoeo_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /raoeo_report - sends current RAOEO status and caches result."""
    global _cached_result

    report = build_raoeo_report()

    # Cache current_result for /raoeo_order (None if already executed today)
    _cached_result = report.get("current_result")

    msg = format_raoeo_report(report)
    if msg:
        await wrap_reply(update, msg, parse_mode='Markdown')
    else:
        await wrap_reply(update, "No RAOEO data available.")


async def cmd_raoeo_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /raoeo_order - executes cached orders."""
    global _cached_result

    # First check if already executed today
    report = build_raoeo_report()
    if report.get("executed_today"):
        await wrap_reply(update, "✅ Already executed today. No new orders to place.")
        return

    if not _cached_result:
        await wrap_reply(update, "⚠️ Not calculated. Use /raoeo_report first.")
        return

    if _cached_result.get('error'):
        await wrap_reply(update, f"⚠️ Cannot execute: {_cached_result['error']}")
        return

    orders = _cached_result.get('orders', [])
    if not orders:
        await wrap_reply(update, "⚠️ No orders to execute.")
        return

    # Execute orders
    await wrap_reply(update, f"⏳ Executing {len(orders)} orders...")

    try:
        exec_results = execute_orders(orders, _cached_result['config'])

        # Format result message
        lines = ["📋 *Execution Results:*"]
        success_count = 0
        for i, res in enumerate(exec_results, 1):
            status = "✅" if res['success'] else "❌"
            if res['success']:
                success_count += 1
            o = res['order']
            lines.append(f"{status} {o['type'].upper()} {o['qty']} @ ${o['price']:.2f}")

        # Save to history
        save_history(_cached_result)
        lines.append(f"\n💾 Saved to history. ({success_count}/{len(orders)} succeeded)")

        # Clear cached result after execution
        _cached_result = None

        await wrap_reply(update, "\n".join(lines), parse_mode='Markdown')

    except Exception as e:
        logging.error(f"[Telegram] Order execution failed: {e}")
        await wrap_reply(update, f"❌ Execution failed: {e}")


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

            # Add command handlers
            _app.add_handler(CommandHandler("raoeo_report", cmd_raoeo_report))
            _app.add_handler(CommandHandler("raoeo_order", cmd_raoeo_order))

            # Send initialization message
            async def send_init_message():
                init_text = (
                    "🤖 *Trading Bot Initialized*\n\n"
                    "Commands:\n"
                    "/raoeo\\_report \\- Current RAOEO status\n"
                    "/raoeo\\_order \\- Execute RAOEO orders"
                )
                try:
                    await wrap_send(init_text, parse_mode='MarkdownV2')
                except Exception as e:
                    logging.error(f"[Telegram] Failed to send init message: {e}")
                    # Fallback to plain text
                    try:
                        fallback_text = "🤖 Trading Bot Initialized\n\nCommands:\n/raoeo_report - Current RAOEO status\n/raoeo_order - Execute RAOEO orders"
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
