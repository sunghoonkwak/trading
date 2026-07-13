# -*- coding: utf-8 -*-
"""Telegram commands for controlling the trading runtime lifecycle."""

import asyncio
import logging
from typing import Any, cast

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from application.runtime_service import RuntimeController

from .utils import wrap_reply

RUNTIME_COMMANDS = {"system_on", "system_off", "system_status"}
RUNTIME_REQUIRED_COMMANDS = {
    "portfolio",
    "gsheet",
    "portfolio_weight",
    "placed_orders",
    "strategy",
    "clear_strategy_history",
    "rebalance",
    "daily_report",
}
RUNTIME_CALLBACK_PREFIXES = (
    "strategy_",
    "reb_",
    "clear_strategy_history_",
)
PENDING_CONFIRMATION_KEY = "runtime_confirmation_pending"


def mark_runtime_confirmation_pending(context: ContextTypes.DEFAULT_TYPE, label: str):
    user_data = getattr(context, "user_data", None)
    if user_data is not None:
        user_data[PENDING_CONFIRMATION_KEY] = label


def clear_runtime_confirmation_pending(context: ContextTypes.DEFAULT_TYPE):
    user_data = getattr(context, "user_data", None)
    if user_data is not None:
        user_data.pop(PENDING_CONFIRMATION_KEY, None)


def get_pending_confirmation_warning() -> str:
    return (
        "\n\n⚠️ 확인 버튼이 활성화된 동안에는 /system_off 를 먼저 실행할 수 없습니다. "
        "실행 또는 취소를 먼저 선택하세요."
    )


def get_initial_control_guide() -> str:
    return (
        "Commands:\n"
        "/system_on - Start trading runtime\n"
        "/system_status - Show runtime state\n"
        "/memo - Add memo"
    )


def get_runtime_control_guide() -> str:
    return (
        "/system_off - Stop trading runtime\n"
        "/system_status - Show runtime state"
    )


def get_runtime_on_guide() -> str:
    from interfaces.telegram.portfolio import get_portfolio_commands_desc

    from .memo import get_memo_commands_desc

    port_desc = get_portfolio_commands_desc().strip()
    memo_desc = get_memo_commands_desc().strip()
    return (
        "Commands:\n"
        f"{get_runtime_control_guide()}\n\n"
        f"{port_desc}\n\n"
        "/strategy - RAOEO & VA Strategies\n"
        "/clear_strategy_history [date] - Clear strategy history for retest\n"
        "/rebalance - TQQQ+SCHD Rebalancing\n\n"
        "/daily_report [date] - View past reports\n"
        f"{memo_desc}"
    )


async def block_runtime_commands_when_off(
    controller: RuntimeController,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if controller.is_running():
        return

    if update.effective_message is None or not update.effective_message.text:
        return

    command = update.effective_message.text.split()[0].lstrip("/").split("@")[0]
    if command not in RUNTIME_REQUIRED_COMMANDS:
        return

    await wrap_reply(
        update,
        "⏸️ <b>Trading runtime is OFF.</b>\n"
        "Use /system_on before trading commands.",
        parse_mode="HTML",
    )
    raise ApplicationHandlerStop


async def block_runtime_callbacks_when_off(
    controller: RuntimeController,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if controller.is_running():
        return

    query = update.callback_query
    if query is None or not query.data:
        return

    if not query.data.startswith(RUNTIME_CALLBACK_PREFIXES):
        return

    await query.answer()
    await wrap_reply(
        update,
        "⏸️ <b>Trading runtime is OFF.</b>\n"
        "Use /system_on before trading actions.",
        parse_mode="HTML",
    )
    clear_runtime_confirmation_pending(context)
    raise ApplicationHandlerStop


async def cmd_system_on(
    controller: RuntimeController,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    logging.info("[TG] /system_on from user")
    await wrap_reply(
        update,
        "⏳ Starting trading runtime...",
        parse_mode="HTML",
    )
    result = await asyncio.to_thread(controller.start)
    if result.success:
        await wrap_reply(
            update,
            f"✅ <b>{result.message}</b>\n\n{get_runtime_on_guide()}",
            parse_mode="HTML",
        )
    else:
        await wrap_reply(
            update,
            f"🚨 <b>Runtime start failed</b>\n"
            f"Component: <code>{result.component or 'unknown'}</code>\n"
            f"{result.message}\n\n"
            f"{get_initial_control_guide()}",
            parse_mode="HTML",
        )


async def cmd_system_off(
    controller: RuntimeController,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    logging.info("[TG] /system_off from user")
    user_data = cast(dict[Any, Any], context.user_data)
    if user_data.get(PENDING_CONFIRMATION_KEY):
        await wrap_reply(
            update,
            "⚠️ <b>확인 버튼이 아직 활성화되어 있습니다.</b>\n"
            "먼저 실행 또는 취소를 선택한 뒤 /system_off 를 다시 실행하세요.",
            parse_mode="HTML",
        )
        return

    result = await asyncio.to_thread(controller.stop)
    icon = "✅" if result.success else "🚨"
    await wrap_reply(
        update,
        f"{icon} <b>{result.message}</b>\n\n{get_initial_control_guide()}",
        parse_mode="HTML",
    )


async def cmd_system_status(
    controller: RuntimeController,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    logging.info("[TG] /system_status from user")
    is_running = controller.is_running()
    status = "ON" if is_running else "OFF"
    await wrap_reply(
        update,
        f"🧭 <b>Trading runtime:</b> <code>{status}</code>\n\n"
        f"{get_runtime_on_guide() if is_running else get_initial_control_guide()}",
        parse_mode="HTML",
    )


class RuntimeCommandHandler:
    """Telegram runtime-control handlers with one explicit controller."""

    def __init__(self, controller: RuntimeController):
        self._controller = controller

    async def block_runtime_commands_when_off(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        return await block_runtime_commands_when_off(self._controller, update, context)

    async def block_runtime_callbacks_when_off(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        return await block_runtime_callbacks_when_off(self._controller, update, context)

    async def cmd_system_on(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await cmd_system_on(self._controller, update, context)

    async def cmd_system_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await cmd_system_off(self._controller, update, context)

    async def cmd_system_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await cmd_system_status(self._controller, update, context)


def register_system_handlers(app: Application, controller: RuntimeController):
    handler = RuntimeCommandHandler(controller)

    app.add_handler(
        MessageHandler(filters.COMMAND, handler.block_runtime_commands_when_off),
        group=-1,
    )
    app.add_handler(
        CallbackQueryHandler(handler.block_runtime_callbacks_when_off),
        group=-1,
    )
    app.add_handler(CommandHandler("system_on", handler.cmd_system_on))
    app.add_handler(CommandHandler("system_off", handler.cmd_system_off))
    app.add_handler(CommandHandler("system_status", handler.cmd_system_status))
