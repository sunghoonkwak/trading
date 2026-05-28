import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telegram_bot import telegram_strategy
from strategy.base import OrderSide, StrategyOrder, StrategyStatus


def test_strategy_command_shows_cash_funding_summary(monkeypatch):
    buy_order = StrategyOrder("SOXL", OrderSide.BUY, 4, 250.0, "Buy Normal")
    funding_order = StrategyOrder("BIL", OrderSide.SELL, 3, 99.0, "cash funding")
    raoeo_report = {
        "date": "2026-05-28",
        "status": StrategyStatus.SKIPPED,
        "orders": [buy_order],
        "pending_orders": [buy_order],
        "info": {"ticker_info": {}},
    }
    va_report = {
        "date": "2026-05-28",
        "status": StrategyStatus.SKIPPED,
        "orders": [],
        "pending_orders": [],
        "info": {},
    }
    monkeypatch.setattr(
        telegram_strategy,
        "run_raoeo_strategy",
        lambda execute=False: raoeo_report,
    )
    monkeypatch.setattr(
        telegram_strategy,
        "run_va_strategy",
        lambda execute=False: va_report,
    )
    monkeypatch.setattr(
        telegram_strategy,
        "prepare_raoeo_cash_funding",
        lambda report: (
            funding_order,
            {
                "buy_budget": 1000.0,
                "orderable_usd": 800.0,
                "shortfall": 200.0,
                "required": True,
                "error": None,
            },
        ),
    )

    replies = []

    async def fake_reply(update, text, **kwargs):
        replies.append(text)

        class Message:
            message_id = 1

        return Message()

    monkeypatch.setattr(telegram_strategy, "wrap_reply", fake_reply)

    class Update:
        pass

    class Context:
        user_data = {}

    result = asyncio.run(telegram_strategy.cmd_strategy(Update(), Context()))

    assert result == telegram_strategy.STRATEGY_CONFIRM
    assert "Buy needed: $1,000.00" in replies[0]
    assert "Orderable USD: $800.00" in replies[0]
    assert "Sell BIL: 3 @ $99.00" in replies[0]
    assert "Est. proceeds: $297.00" in replies[0]


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


def test_execute_without_cash_sale_skips_funding_and_runs_strategies(monkeypatch):
    monkeypatch.setattr(
        telegram_strategy,
        "execute_raoeo_cash_funding",
        lambda: (_ for _ in ()).throw(
            AssertionError("cash funding must be skipped")
        ),
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
        lambda raoeo, va: formatted.append((raoeo, va)) or "final report",
    )

    async def fake_edit(update, text, **kwargs):
        return None

    monkeypatch.setattr(telegram_strategy, "wrap_edit", fake_edit)

    class Query:
        data = "strategy_without_cash_sale"

        async def answer(self):
            return None

    class Update:
        callback_query = Query()

    class Context:
        user_data = {"strategy_raoeo": {"date": "2026-05-27"}}

    asyncio.run(telegram_strategy.handle_strategy_callback(Update(), Context()))

    assert calls == [("raoeo", True), ("va", True)]
    assert len(formatted) == 1
