import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from telegram_bot import telegram_portfolio, telegram_strategy
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
        "run_strategy_suite",
        lambda execute=False: (raoeo_report, va_report),
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
        lambda report=None: (funding_result, {"required": True}),
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
        "run_strategy_suite",
        lambda execute=False: (_ for _ in ()).throw(
            AssertionError("strategies must stop")
        ),
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
        lambda report=None: (funding_result, {"required": True}),
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
        "run_strategy_suite",
        lambda execute=False: calls.append(("suite", execute)) or (
            {"date": "2026-05-27"},
            {},
        ),
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

    assert calls == [("suite", True)]
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
        "run_strategy_suite",
        lambda execute=False: calls.append(("suite", execute)) or (
            {"date": "2026-05-27"},
            {},
        ),
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

    assert calls == [("suite", True)]
    assert len(formatted) == 1


def test_portfolio_weight_command_uses_valid_portfolio_scope(monkeypatch):
    captured = {}

    def fake_get_weight_diffs(scope="all"):
        captured["scope"] = scope
        return [], 0.0, {"current": 0.0, "target": 0.1}

    class ImmediateResult:
        def __init__(self, value):
            self.value = value

        def __await__(self):
            yield
            return self.value

    class FakeLoop:
        def run_in_executor(self, executor, func, *args):
            return ImmediateResult(func(*args))

    replies = []

    async def fake_reply(update, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(
        telegram_portfolio.asyncio,
        "get_running_loop",
        lambda: FakeLoop(),
    )
    monkeypatch.setattr(telegram_portfolio, "get_weight_diffs", fake_get_weight_diffs)
    monkeypatch.setattr(
        telegram_portfolio,
        "format_weight_diffs",
        lambda diffs, total_usd, cash_info: "weights",
    )
    monkeypatch.setattr(telegram_portfolio, "wrap_reply", fake_reply)

    class Update:
        pass

    class Context:
        user_data = {}

    asyncio.run(telegram_portfolio.cmd_portfolio_weight(Update(), Context()))

    assert captured == {"scope": "all"}
    assert replies


def test_format_weight_diffs_shows_group_total_and_main_ticker(monkeypatch):
    monkeypatch.setattr(
        telegram_portfolio,
        "get_fear_and_greed",
        lambda: 50,
        raising=False,
    )

    text = telegram_portfolio.format_weight_diffs(
        [
            {
                "ticker": "QQQM",
                "name": "Nasdaq100",
                "cur_w": 0.40,
                "tgt_w": 0.60,
                "diff": 0.20,
                "abs_diff": 0.20,
                "qty_diff": 10,
                "is_group": True,
                "current_value_usd": 4000,
                "target_value_usd": 6000,
            }
        ],
        10000,
        {"current": 0.20, "target": 0.20},
    )

    assert "<b>Nasdaq100</b> [QQQM]" in text
    assert "$4.0K → $6.0K" in text
    assert "Qty: +10 QQQM" in text
