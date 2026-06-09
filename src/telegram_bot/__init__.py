# -*- coding: utf-8 -*-
"""Telegram package with lazy public exports."""

__all__ = ["initialize_telegram", "wrap_reply", "wrap_send"]


def __getattr__(name):
    if name == "initialize_telegram":
        from .telegram_bot import initialize_telegram

        return initialize_telegram
    if name in {"wrap_reply", "wrap_send"}:
        from . import telegram_utils

        return getattr(telegram_utils, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
