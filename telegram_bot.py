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


def format_telegram_message(report: dict) -> str:
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


async def send_notification(message: str) -> bool:
    """
    Send a notification message via Telegram.

    Args:
        message: Message to send

    Returns:
        bool: True if sent successfully
    """
    global _app, _chat_id

    if not _app or not _chat_id:
        logging.warning("Telegram not initialized")
        return False

    try:
        await _app.bot.send_message(
            chat_id=_chat_id,
            text=message,
            parse_mode='Markdown'
        )
        logging.info(f"Telegram message sent: {message}")
        return True
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")
        return False


async def cmd_raoeo_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /raoeo_report - sends current RAOEO status and caches result."""
    global _cached_result

    report = build_raoeo_report()

    # Cache current_result for /raoeo_order (None if already executed today)
    _cached_result = report.get("current_result")

    msg = format_telegram_message(report)
    if msg:
        await update.message.reply_text(msg, parse_mode='Markdown')
    else:
        await update.message.reply_text("No RAOEO data available.")


async def cmd_raoeo_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /raoeo_order - executes cached orders."""
    global _cached_result

    # First check if already executed today
    report = build_raoeo_report()
    if report.get("executed_today"):
        await update.message.reply_text("✅ Already executed today. No new orders to place.")
        return

    if not _cached_result:
        await update.message.reply_text("⚠️ Not calculated. Use /raoeo_report first.")
        return

    if _cached_result.get('error'):
        await update.message.reply_text(f"⚠️ Cannot execute: {_cached_result['error']}")
        return

    orders = _cached_result.get('orders', [])
    if not orders:
        await update.message.reply_text("⚠️ No orders to execute.")
        return

    # Execute orders
    await update.message.reply_text(f"⏳ Executing {len(orders)} orders...")

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

        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')

    except Exception as e:
        logging.error(f"[Telegram] Order execution failed: {e}")
        await update.message.reply_text(f"❌ Execution failed: {e}")


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
                logging.debug(f"[Telegram] Sending init message: {repr(init_text)}")
                try:
                    await _app.bot.send_message(
                        chat_id=_chat_id,
                        text=init_text,
                        parse_mode='MarkdownV2'
                    )
                    logging.info("[Telegram] Init message sent successfully")
                except Exception as e:
                    logging.error(f"[Telegram] Failed to send init message: {e}")
                    # Fallback to plain text
                    try:
                        await _app.bot.send_message(
                            chat_id=_chat_id,
                            text="🤖 Trading Bot Initialized\n\nCommands:\n/raoeo_report - Current RAOEO status\n/raoeo_order - Execute RAOEO orders"
                        )
                        logging.info("[Telegram] Init message sent (plain text fallback)")
                    except Exception as e2:
                        logging.error(f"[Telegram] Fallback also failed: {e2}")

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
