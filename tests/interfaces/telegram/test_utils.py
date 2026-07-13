import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from telegram.error import TimedOut

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from interfaces.telegram import utils as telegram_utils


class FakeMessage:
    def __init__(self, failures=0):
        self.failures = failures
        self.calls = []

    async def reply_text(self, text, **kwargs):
        self.calls.append((text, kwargs))
        if self.failures:
            self.failures -= 1
            raise TimedOut("slow")
        return "replied"


class FakeCallback:
    def __init__(self, message=None):
        self.message = message
        self.calls = []

    async def edit_message_text(self, text, **kwargs):
        self.calls.append((text, kwargs))
        return "edited"


class FakeBot:
    def __init__(self, failure=None):
        self.failure = failure
        self.sent = []
        self.edited = []

    async def send_message(self, **kwargs):
        self.sent.append(kwargs)
        if self.failure:
            raise self.failure
        return "sent"

    async def edit_message_text(self, **kwargs):
        self.edited.append(kwargs)
        return "edited"


@pytest.fixture(autouse=True)
def reset_telegram_utils(monkeypatch):
    alerts = []
    monkeypatch.setattr(telegram_utils, "_add_alert", lambda *args: alerts.append(args))
    monkeypatch.setattr(telegram_utils, "_bot", None)
    monkeypatch.setattr(telegram_utils, "_chat_id", None)
    monkeypatch.setattr(telegram_utils, "_main_loop", None)
    monkeypatch.setattr(telegram_utils, "RETRY_DELAY", 0)
    return alerts


def test_wrap_reply_uses_message_and_callback_fallback(reset_telegram_utils):
    message = FakeMessage()
    update = SimpleNamespace(message=message, callback_query=None)

    assert asyncio.run(
        telegram_utils.wrap_reply(update, "hello\nworld", parse_mode="HTML"),
    ) == "replied"

    fallback = FakeMessage()
    callback_update = SimpleNamespace(
        message=None,
        callback_query=SimpleNamespace(message=fallback),
    )
    assert asyncio.run(
        telegram_utils.wrap_reply(callback_update, "fallback"),
    ) == "replied"
    assert reset_telegram_utils[0] == ("[TG] hello", "INFO")


def test_wrap_reply_retries_timeout_and_empty_update():
    message = FakeMessage(failures=1)
    update = SimpleNamespace(message=message, callback_query=None)

    assert asyncio.run(telegram_utils.wrap_reply(update, "retry")) == "replied"
    assert len(message.calls) == 2

    empty = SimpleNamespace(message=None, callback_query=None)
    assert asyncio.run(telegram_utils.wrap_reply(empty, "nothing")) is None
    assert asyncio.run(telegram_utils.wrap_reply(empty, "")) is None


def test_wrap_reply_raises_after_final_timeout(monkeypatch, reset_telegram_utils):
    monkeypatch.setattr(telegram_utils, "MAX_RETRIES", 0)
    update = SimpleNamespace(
        message=FakeMessage(failures=1),
        callback_query=None,
    )

    with pytest.raises(TimedOut):
        asyncio.run(telegram_utils.wrap_reply(update, "fails"))

    assert reset_telegram_utils[-1][1] == "ERROR"


def test_wrap_edit_edits_callback_and_handles_missing_query():
    callback = FakeCallback()
    update = SimpleNamespace(callback_query=callback)

    assert asyncio.run(
        telegram_utils.wrap_edit(update, "changed", parse_mode="HTML"),
    ) == "edited"
    assert callback.calls == [("changed", {"parse_mode": "HTML"})]
    assert asyncio.run(telegram_utils.wrap_edit(None, "missing")) is None
    assert asyncio.run(telegram_utils.wrap_edit(update, "")) is None


def test_wrap_send_and_edit_message_use_configured_bot():
    async def exercise():
        bot = FakeBot()
        telegram_utils.set_telegram_bot(bot, "chat")

        sent = await telegram_utils.wrap_send("notice", parse_mode="HTML")
        edited = await telegram_utils.wrap_edit_message(
            "other-chat",
            7,
            "revised",
        )
        return bot, sent, edited

    bot, sent, edited = asyncio.run(exercise())

    assert sent == "sent"
    assert edited == "edited"
    assert bot.sent[0]["chat_id"] == "chat"
    assert bot.edited[0]["message_id"] == 7


def test_send_wrappers_return_when_unconfigured_or_empty():
    assert asyncio.run(telegram_utils.wrap_send("notice")) is None
    assert asyncio.run(
        telegram_utils.wrap_edit_message("chat", 1, "notice"),
    ) is None

    async def exercise_empty():
        telegram_utils.set_telegram_bot(FakeBot(), "chat")
        assert await telegram_utils.wrap_send("") is None
        assert await telegram_utils.wrap_edit_message("chat", 1, "") is None

    asyncio.run(exercise_empty())


def test_set_telegram_bot_without_running_loop(caplog):
    telegram_utils.set_telegram_bot(FakeBot(), "chat")

    assert telegram_utils._main_loop is None
    assert "without a running loop" in caplog.text


def test_send_notification_schedules_on_current_loop(reset_telegram_utils):
    async def exercise():
        bot = FakeBot()
        telegram_utils.set_telegram_bot(bot, "chat")
        telegram_utils.send_notification("filled\norder")
        await asyncio.sleep(0)
        return bot

    bot = asyncio.run(exercise())

    assert bot.sent == [
        {
            "chat_id": "chat",
            "text": "filled\norder",
            "parse_mode": "HTML",
        }
    ]
    assert ("[TG] filled", "INFO") in reset_telegram_utils


def test_send_notification_ignores_missing_state_and_empty_text():
    telegram_utils.send_notification("notice")

    async def exercise():
        telegram_utils.set_telegram_bot(FakeBot(), "chat")
        telegram_utils.send_notification("")
        await asyncio.sleep(0)

    asyncio.run(exercise())
