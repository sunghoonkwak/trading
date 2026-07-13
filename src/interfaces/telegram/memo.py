# -*- coding: utf-8 -*-
"""
Telegram Memo Module

Telegram memo transport adapter.
"""
import html
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, cast
from zoneinfo import ZoneInfo

from telegram import Message, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from core import display

from .utils import wrap_reply


@dataclass(frozen=True)
class MemoStore:
    load: Callable[[], dict]
    save: Callable[[dict], bool]


async def _handle_text_message(
    store: MemoStore,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Handle non-command text messages and save to memo.json."""
    message = cast(Message, update.message)
    text = cast(str, message.text).strip()
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
    messages = store.load()
    if date_key not in messages:
        messages[date_key] = []
    messages[date_key].append(entry)
    store.save(messages)

    # Calculate today count and weekly total
    today_count = len(messages.get(date_key, []))
    kst = ZoneInfo("Asia/Seoul")
    today_date = datetime.now(kst).date()
    week_dates = [(today_date - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    weekly_total = sum(len(messages.get(d, [])) for d in week_dates)

    logging.info(f"[Memo] Saved: {text[:50]}...")
    display.add_alert(f'[TG] <= "{text[:60]}"')
    await wrap_reply(update, f"📝 Saved (today: {today_count}, total: {weekly_total})")


async def _cmd_memo(
    store: MemoStore,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Command handler for /memo - show recent 7 days of messages."""
    logging.info("[TG] /memo from user")
    messages = store.load()
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


class MemoCommandHandler:
    """Telegram memo handlers with one explicit persistence store."""

    def __init__(self, store: MemoStore):
        self._store = store

    async def handle_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        return await _handle_text_message(self._store, update, context)

    async def cmd_memo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await _cmd_memo(self._store, update, context)


def register_memo_handler(app: Application, store: MemoStore):
    """Register memo handler for non-command text messages."""
    handler = MemoCommandHandler(store)

    app.add_handler(CommandHandler("memo", handler.cmd_memo))
    # Handle all text messages that are NOT commands
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler.handle_text_message))


def get_memo_commands_desc() -> str:
    """Return memo command descriptions for init message."""
    return "/memo - View recent memos (1 week)"
