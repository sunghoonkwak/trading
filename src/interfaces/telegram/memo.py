# -*- coding: utf-8 -*-
"""
Telegram Memo Module

Telegram memo transport adapter.
"""
import html
import logging
from contextlib import contextmanager
from contextvars import ContextVar
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


_memo_store: ContextVar[MemoStore | None] = ContextVar("telegram_memo_store", default=None)


def _require_memo_store() -> tuple[Callable[[], dict], Callable[[dict], bool]]:
    store = _memo_store.get()
    if store is None:
        raise RuntimeError("Memo command is not bound to a Telegram factory.")
    return store.load, store.save


@contextmanager
def bind_memo_store(store: MemoStore):
    """Bind one persistence store for focused direct-handler tests."""
    token = _memo_store.set(store)
    try:
        yield
    finally:
        _memo_store.reset(token)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    load_memos, save_memos = _require_memo_store()
    messages = load_memos()
    if date_key not in messages:
        messages[date_key] = []
    messages[date_key].append(entry)
    save_memos(messages)

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
    logging.info("[TG] /memo from user")
    load_memos, _ = _require_memo_store()
    messages = load_memos()
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


def register_memo_handler(app: Application, store: MemoStore):
    """Register memo handler for non-command text messages."""
    def bind(handler):
        async def bound(update, context):
            token = _memo_store.set(store)
            try:
                return await handler(update, context)
            finally:
                _memo_store.reset(token)

        return bound

    app.add_handler(CommandHandler("memo", bind(cmd_memo)))
    # Handle all text messages that are NOT commands
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bind(handle_text_message)))


def get_memo_commands_desc() -> str:
    """Return memo command descriptions for init message."""
    return "/memo - View recent memos (1 week)"
