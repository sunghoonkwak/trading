import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telegram_bot import telegram_strategy
from telegram_bot.telegram_strategy import build_confirm_keyboard
from strategy.base import OrderSide, StrategyOrder


def _callback_data(keyboard):
    return [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]


def test_strategy_keyboard_has_two_options_when_cash_funding_is_not_required():
    keyboard = build_confirm_keyboard(has_orders=True, cash_funding_required=False)

    assert _callback_data(keyboard) == ["strategy_without_cash_sale", "strategy_no"]


def test_strategy_keyboard_has_three_options_when_cash_funding_is_required():
    keyboard = build_confirm_keyboard(has_orders=True, cash_funding_required=True)

    assert _callback_data(keyboard) == [
        "strategy_with_cash_sale",
        "strategy_without_cash_sale",
        "strategy_no",
    ]


def test_failed_cash_funding_stops_all_strategy_execution(monkeypatch):
    funding_result = {
        "order": StrategyOrder("BIL", OrderSide.SELL, 10, 99.0, "funding"),
        "success": False,
        "message": "rejected",
    }
    monkeypatch.setattr(
        telegram_strategy,
        "execute_raoeo_cash_funding",
        lambda: (funding_result, {"required": True}),
        raising=False,
    )
    monkeypatch.setattr(
        telegram_strategy,
        "save_raoeo_cash_funding_result",
        lambda today, result: None,
        raising=False,
    )
    monkeypatch.setattr(
        telegram_strategy,
        "run_raoeo_strategy",
        lambda execute=False: (_ for _ in ()).throw(AssertionError("RAOEO must stop")),
    )
    monkeypatch.setattr(
        telegram_strategy,
        "run_va_strategy",
        lambda execute=False: (_ for _ in ()).throw(AssertionError("VA must stop")),
    )

    edits = []

    async def fake_edit(update, text, **kwargs):
        edits.append(text)

    monkeypatch.setattr(telegram_strategy, "wrap_edit", fake_edit)

    class Query:
        data = "strategy_with_cash_sale"

        async def answer(self):
            return None

    class Update:
        callback_query = Query()

    class Context:
        user_data = {}

    asyncio.run(telegram_strategy.handle_strategy_callback(Update(), Context()))

    assert "Cash funding failed" in edits[-1]


def test_successful_cash_funding_runs_strategies_and_reports_sale(monkeypatch):
    funding_result = {
        "order": StrategyOrder("BIL", OrderSide.SELL, 10, 99.0, "funding"),
        "success": True,
        "message": "Success",
    }
    monkeypatch.setattr(
        telegram_strategy,
        "execute_raoeo_cash_funding",
        lambda: (funding_result, {"required": True}),
    )
    saved = []
    monkeypatch.setattr(
        telegram_strategy,
        "save_raoeo_cash_funding_result",
        lambda today, result: saved.append((today, result)),
    )
    calls = []
    monkeypatch.setattr(
        telegram_strategy,
        "run_raoeo_strategy",
        lambda execute=False: calls.append(("raoeo", execute)) or {"date": "2026-05-27"},
    )
    monkeypatch.setattr(
        telegram_strategy,
        "run_va_strategy",
        lambda execute=False: calls.append(("va", execute)) or {},
    )
    formatted = []
    monkeypatch.setattr(
        telegram_strategy,
        "format_strategy_report",
        lambda raoeo, va: formatted.append(raoeo) or "final report",
    )

    async def fake_edit(update, text, **kwargs):
        return None

    monkeypatch.setattr(telegram_strategy, "wrap_edit", fake_edit)

    class Query:
        data = "strategy_with_cash_sale"

        async def answer(self):
            return None

    class Update:
        callback_query = Query()

    class Context:
        user_data = {"strategy_raoeo": {"date": "2026-05-27"}}

    asyncio.run(telegram_strategy.handle_strategy_callback(Update(), Context()))

    assert calls == [("raoeo", True), ("va", True)]
    assert saved == [("2026-05-27", funding_result)]
    assert formatted[0]["cash_funding_results"] == [funding_result]
