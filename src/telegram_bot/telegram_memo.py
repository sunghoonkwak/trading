# -*- coding: utf-8 -*-
"""
Telegram Memo Module

Saves arbitrary text messages to message.json for later review.
"""
import os
import json
import html
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from .telegram_utils import wrap_reply
import display

# Path to memo.json in KIS_config folder
CONFIG_ROOT = os.path.join(os.path.expanduser("~"), "KIS_config")
MEMO_FILE = os.path.join(CONFIG_ROOT, "memo.json")


def load_messages() -> dict:
    """Load existing messages from memo.json."""
    if not os.path.exists(MEMO_FILE):
        return {}
    try:
        with open(MEMO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        logging.error(f"[Memo] Failed to load messages: {e}")
        return {}


def save_messages(messages: dict):
    """Save messages to memo.json."""
    with open(MEMO_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle non-command text messages and save to message.json."""
    text = update.message.text.strip()
    if not text:
        return

    # Get current time in KST
    kst = ZoneInfo("Asia/Seoul")
    now = datetime.now(kst)
    date_key = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    # Format: "hh:mm:ss : message"
    entry = f"{time_str} : {text}"

    # Load, append to date, save
    messages = load_messages()
    if date_key not in messages:
        messages[date_key] = []
    messages[date_key].append(entry)
    save_messages(messages)

    # Calculate today count and weekly total
    today_count = len(messages.get(date_key, []))
    kst = ZoneInfo("Asia/Seoul")
    today_date = datetime.now(kst).date()
    week_dates = [(today_date - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    weekly_total = sum(len(messages.get(d, [])) for d in week_dates)

    logging.info(f"[Memo] Saved: {text[:50]}...")
    display.add_alert(f'[TG] <= "{text[:60]}"')
    await wrap_reply(update, f"📝 Saved (today: {today_count}, total: {weekly_total})")


async def cmd_memo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /memo - show recent 7 days of messages."""
    messages = load_messages()
    if not messages:
        await wrap_reply(update, "📭 No saved messages.")
        return

    # Get recent 7 days
    kst = ZoneInfo("Asia/Seoul")
    today = datetime.now(kst).date()
    recent_dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    lines = ["📋 <b>Recent Memos (1 week)</b>"]
    found = False
    for date_key in recent_dates:
        if date_key in messages:
            found = True
            lines.append(f"\n<b>{date_key}</b>")
            for entry in messages[date_key]:
                lines.append(f"  • {html.escape(entry)}")

    if not found:
        await wrap_reply(update, "📭 No messages in last week.")
        return

    await wrap_reply(update, "\n".join(lines), parse_mode='HTML')


def register_memo_handler(app: Application):
    """Register memo handler for non-command text messages."""
    app.add_handler(CommandHandler("memo", cmd_memo))
    # Handle all text messages that are NOT commands
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))


def get_memo_commands_desc() -> str:
    """Return memo command descriptions for init message."""
    return "/memo - View recent memos (1 week)"
