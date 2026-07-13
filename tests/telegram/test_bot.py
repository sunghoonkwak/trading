import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from domain.strategy.base import OrderSide, StrategyOrder, StrategyStatus
from interfaces.telegram import memo as telegram_memo
from interfaces.telegram import portfolio as telegram_portfolio
from interfaces.telegram import rebalancing as telegram_rebalancing
from interfaces.telegram import strategy as telegram_strategy


def _portfolio_dependencies(**overrides):
    defaults = {
        "reader": SimpleNamespace(get_portfolio_data=lambda: {}),
        "market_reader": SimpleNamespace(
            get_current_price=lambda _ticker: 0.0,
            fetch_price=lambda _ticker: 0.0,
        ),
        "order_reader": SimpleNamespace(fetch_open_orders=lambda: (None, 0, 0, 0)),
        "get_weight_diffs": lambda _scope: ([], 0.0, {}),
        "refresh_gsheet_cache": lambda: {},
    }
    defaults.update(overrides)
    return telegram_portfolio.PortfolioCommandDependencies(**defaults)


def _strategy_dependencies(**overrides):
    def normalize_date(value):
        if len(value) == 8 and value.isdigit():
            value = f"{value[:4]}-{value[4:6]}-{value[6:]}"
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")

    defaults = {
        "strategy_run_service": SimpleNamespace(run_suite=lambda *, execute: ({}, {})),
        "clear_history": lambda _date: {"removed": False, "date": _date},
        "normalize_history_date": normalize_date,
        "prepare_cash_funding": lambda _report: (None, {"required": False}),
        "execute_cash_funding": lambda _report: (None, {"required": False}),
        "save_cash_funding_result": lambda _date, _result: None,
    }
    defaults.update(overrides)
    return telegram_strategy.StrategyCommandDependencies(**defaults)


def test_telegram_strategy_handler_uses_application_service(monkeypatch):
    class Service:
        def run_suite(self, *, execute):
            return ({"execute": execute}, {})

    handler = telegram_strategy.StrategyCommandHandler(
        _strategy_dependencies(strategy_run_service=Service())
    )

    assert handler.run_strategy_suite(execute=True) == ({"execute": True}, {})


def test_telegram_rebalancing_uses_application_facade(monkeypatch):
    class Service:
        def run_rebalancing(self, *, execute):
            return {"execute": execute}

    handler = telegram_rebalancing.RebalancingCommandHandler(Service())

    assert handler.run_rebalancing_strategy(execute=True) == {"execute": True}


def test_memo_handler_uses_its_own_store(monkeypatch):
    replies = []

    async def fake_reply(update, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(telegram_memo, "wrap_reply", fake_reply)
    handler = telegram_memo.MemoCommandHandler(
        telegram_memo.MemoStore(
            load=lambda: {}, save=lambda _memos: True, add_alert=lambda _message: None
        )
    )

    class Update:
        pass

    class Context:
        pass

    asyncio.run(handler.cmd_memo(Update(), Context()))

    assert replies == ["📭 No saved messages."]


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
    handler = telegram_strategy.StrategyCommandHandler(_strategy_dependencies(
        strategy_run_service=SimpleNamespace(
            run_suite=lambda *, execute: (raoeo_report, va_report)
        ),
        prepare_cash_funding=lambda report: (
            funding_order,
            {
                "buy_budget": 1000.0,
                "orderable_usd": 800.0,
                "shortfall": 200.0,
                "required": True,
                "error": None,
            },
        ),
    ))

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

    result = asyncio.run(handler.cmd_strategy(Update(), Context()))

    assert result == telegram_strategy.STRATEGY_CONFIRM
    assert "Buy needed: $1,000.00" in replies[0]
    assert "Orderable USD: $800.00" in replies[0]
    assert "Sell BIL: 3 @ $99.00" in replies[0]
    assert "Est. proceeds: $297.00" in replies[0]


def test_system_guides_split_off_initial_and_on_runtime_commands():
    from interfaces.telegram import system as telegram_system

    initial = telegram_system.get_initial_control_guide()
    runtime = telegram_system.get_runtime_on_guide()

    assert "/system_on" in initial
    assert "/memo" in initial
    assert "/system_off" not in initial
    assert "/system_off" in runtime
    assert "/strategy" in runtime
    assert "/rebalance" in runtime


def test_strategy_confirmation_guides_before_system_off(monkeypatch):
    buy_order = StrategyOrder("SOXL", OrderSide.BUY, 1, 250.0, "Buy Normal")
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
    handler = telegram_strategy.StrategyCommandHandler(_strategy_dependencies(
        strategy_run_service=SimpleNamespace(
            run_suite=lambda *, execute: (raoeo_report, va_report)
        ),
        prepare_cash_funding=lambda report: (None, {"required": False, "error": None}),
    ))
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

    result = asyncio.run(handler.cmd_strategy(Update(), Context()))

    assert result == telegram_strategy.STRATEGY_CONFIRM
    assert "/system_off" in replies[0]
    assert "취소" in replies[0]
    assert Context.user_data["runtime_confirmation_pending"] == "strategy"


def test_system_off_is_blocked_while_confirmation_is_pending(monkeypatch):
    from application.runtime_service import RuntimeCommandResult, RuntimeController
    from interfaces.telegram import system as telegram_system

    stop_calls = []
    replies = []
    controller = RuntimeController(
        start=lambda: RuntimeCommandResult(True, "ON"),
        stop=lambda: stop_calls.append("stop") or RuntimeCommandResult(True, "OFF"),
        is_running=lambda: True,
    )

    async def fake_reply(update, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(telegram_system, "wrap_reply", fake_reply)

    class Update:
        message = object()
        callback_query = None

    class Context:
        user_data = {"runtime_confirmation_pending": "strategy"}

    handler = telegram_system.RuntimeCommandHandler(controller)
    asyncio.run(handler.cmd_system_off(Update(), Context()))

    assert stop_calls == []
    assert "/system_off" in replies[0]
    assert "확인" in replies[0]


def test_runtime_callback_is_blocked_when_runtime_is_off(monkeypatch):
    from telegram.ext import ApplicationHandlerStop

    from application.runtime_service import RuntimeCommandResult, RuntimeController
    from interfaces.telegram import system as telegram_system

    replies = []
    controller = RuntimeController(
        start=lambda: RuntimeCommandResult(True, "ON"),
        stop=lambda: RuntimeCommandResult(True, "OFF"),
        is_running=lambda: False,
    )

    async def fake_reply(update, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(telegram_system, "wrap_reply", fake_reply)

    class Query:
        data = "strategy_without_cash_sale"

        async def answer(self):
            return None

    class Update:
        callback_query = Query()
        effective_message = object()

    class Context:
        user_data = {}

    try:
        handler = telegram_system.RuntimeCommandHandler(controller)
        asyncio.run(handler.block_runtime_callbacks_when_off(Update(), Context()))
    except ApplicationHandlerStop:
        stopped = True
    else:
        stopped = False

    assert stopped is True
    assert "OFF" in replies[0]


def test_failed_cash_funding_stops_all_strategy_execution(monkeypatch):
    funding_result = {
        "order": StrategyOrder("BIL", OrderSide.SELL, 10, 99.0, "funding"),
        "success": False,
        "message": "rejected",
    }
    handler = telegram_strategy.StrategyCommandHandler(_strategy_dependencies(
        strategy_run_service=SimpleNamespace(
            run_suite=lambda *, execute: (_ for _ in ()).throw(
                AssertionError("strategies must stop")
            )
        ),
        execute_cash_funding=lambda report=None: (funding_result, {"required": True}),
    ))

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

    asyncio.run(handler.handle_strategy_callback(Update(), Context()))

    assert "Cash funding failed" in edits[-1]


def test_successful_cash_funding_runs_strategies_and_reports_sale(monkeypatch):
    funding_result = {
        "order": StrategyOrder("BIL", OrderSide.SELL, 10, 99.0, "funding"),
        "success": True,
        "message": "Success",
    }
    saved = []
    calls = []
    handler = telegram_strategy.StrategyCommandHandler(_strategy_dependencies(
        strategy_run_service=SimpleNamespace(
            run_suite=lambda *, execute: calls.append(("suite", execute)) or (
                {"date": "2026-05-27"}, {}
            )
        ),
        execute_cash_funding=lambda report=None: (funding_result, {"required": True}),
        save_cash_funding_result=lambda today, result: saved.append((today, result)),
    ))
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

    asyncio.run(handler.handle_strategy_callback(Update(), Context()))

    assert calls == [("suite", True)]
    assert saved == [("2026-05-27", funding_result)]
    assert formatted[0]["cash_funding_results"] == [funding_result]


def test_execute_without_cash_sale_skips_funding_and_runs_strategies(monkeypatch):
    calls = []
    handler = telegram_strategy.StrategyCommandHandler(_strategy_dependencies(
        strategy_run_service=SimpleNamespace(
            run_suite=lambda *, execute: calls.append(("suite", execute)) or (
                {"date": "2026-05-27"}, {}
            )
        ),
        execute_cash_funding=lambda: (_ for _ in ()).throw(
            AssertionError("cash funding must be skipped")
        ),
    ))
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

    asyncio.run(handler.handle_strategy_callback(Update(), Context()))

    assert calls == [("suite", True)]
    assert len(formatted) == 1


def test_clear_strategy_history_accepts_compact_date(monkeypatch):
    replies = []

    async def fake_reply(update, text, **kwargs):
        replies.append((text, kwargs))

    monkeypatch.setattr(telegram_strategy, "wrap_reply", fake_reply)

    class Update:
        pass

    class Context:
        args = ["20260630"]

    handler = telegram_strategy.StrategyCommandHandler(_strategy_dependencies())
    asyncio.run(handler.cmd_clear_strategy_history(Update(), Context()))

    text, kwargs = replies[0]
    assert "2026-06-30" in text
    keyboard = kwargs["reply_markup"].inline_keyboard
    assert keyboard[0][0].callback_data == "clear_strategy_history_yes:2026-06-30"
    assert len(keyboard[0][0].callback_data.encode("utf-8")) <= 64


def test_clear_strategy_history_rejects_invalid_date(monkeypatch):
    replies = []
    cleared = []

    async def fake_reply(update, text, **kwargs):
        replies.append((text, kwargs))

    monkeypatch.setattr(telegram_strategy, "wrap_reply", fake_reply)

    class Update:
        pass

    class Context:
        args = ["<bad&date>" * 20]

    handler = telegram_strategy.StrategyCommandHandler(_strategy_dependencies(
        clear_history=lambda target_date: cleared.append(target_date)
    ))
    asyncio.run(handler.cmd_clear_strategy_history(Update(), Context()))

    text, kwargs = replies[0]
    assert "Invalid date" in text
    assert "&lt;bad&amp;date&gt;" in text
    assert "reply_markup" not in kwargs
    assert cleared == []


def test_clear_strategy_history_rejects_impossible_date(monkeypatch):
    replies = []

    async def fake_reply(update, text, **kwargs):
        replies.append((text, kwargs))

    monkeypatch.setattr(telegram_strategy, "wrap_reply", fake_reply)

    class Update:
        pass

    class Context:
        args = ["2026-99-99"]

    handler = telegram_strategy.StrategyCommandHandler(_strategy_dependencies())
    asyncio.run(handler.cmd_clear_strategy_history(Update(), Context()))

    text, kwargs = replies[0]
    assert "Invalid date" in text
    assert "2026-99-99" in text
    assert "reply_markup" not in kwargs


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

    handler = telegram_portfolio.PortfolioCommandHandler(
        _portfolio_dependencies(get_weight_diffs=fake_get_weight_diffs)
    )
    asyncio.run(handler.cmd_portfolio_weight(Update(), Context()))

    assert captured == {"scope": "all"}
    assert replies


def test_portfolio_command_preserves_dependencies_in_executor(monkeypatch):
    replies = []

    async def fake_reply(update, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(telegram_portfolio, "wrap_reply", fake_reply)
    monkeypatch.setattr(telegram_portfolio, "format_portfolio_summary", lambda _data: "summary")
    monkeypatch.setattr(telegram_portfolio, "build_ticker_keyboard", lambda _data: None)

    class Update:
        pass

    class Context:
        user_data = {}

    dependencies = _portfolio_dependencies(
        reader=SimpleNamespace(get_portfolio_data=lambda: {"merged_data": {}})
    )

    handler = telegram_portfolio.PortfolioCommandHandler(dependencies)
    result = asyncio.run(handler.cmd_portfolio(Update(), Context()))

    assert result == telegram_portfolio.SELECT_TICKER
    assert replies == ["summary"]


def test_ticker_keyboard_loads_stock_config_from_src_root(monkeypatch, tmp_path):
    module_path = tmp_path / "src" / "interfaces" / "telegram" / "portfolio.py"
    module_path.parent.mkdir(parents=True)
    module_path.touch()
    (tmp_path / "src" / "stock_configuration.json").write_text(
        json.dumps({"KR": [], "US": [{"ticker": "QQQ", "telegram_button": True}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(telegram_portfolio, "__file__", str(module_path))

    keyboard = telegram_portfolio.build_ticker_keyboard({"merged_data": {}})

    assert keyboard.inline_keyboard[0][0].text == "QQQ"


def test_portfolio_handlers_keep_factory_dependencies_isolated(monkeypatch):
    monkeypatch.setattr(telegram_portfolio, "format_portfolio_summary", lambda data: data["name"])
    monkeypatch.setattr(telegram_portfolio, "build_ticker_keyboard", lambda _data: None)

    replies = []

    async def fake_reply(update, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(telegram_portfolio, "wrap_reply", fake_reply)

    class Update:
        pass

    class Context:
        def __init__(self):
            self.user_data = {}

    first = telegram_portfolio.PortfolioCommandHandler(
        _portfolio_dependencies(reader=SimpleNamespace(get_portfolio_data=lambda: {"name": "first"}))
    )
    second = telegram_portfolio.PortfolioCommandHandler(
        _portfolio_dependencies(reader=SimpleNamespace(get_portfolio_data=lambda: {"name": "second"}))
    )

    asyncio.run(first.cmd_portfolio(Update(), Context()))
    asyncio.run(second.cmd_portfolio(Update(), Context()))

    assert replies == ["first", "second"]


def test_gsheet_command_refreshes_only_gsheet_cache(monkeypatch):
    replies = []

    async def fake_reply(update, text, **kwargs):
        replies.append(text)

    class ImmediateResult:
        def __init__(self, value):
            self.value = value

        def __await__(self):
            yield
            return self.value

    class FakeLoop:
        def run_in_executor(self, executor, func, *args):
            return ImmediateResult(func(*args))

    monkeypatch.setattr(
        telegram_portfolio.asyncio,
        "get_running_loop",
        lambda: FakeLoop(),
    )
    monkeypatch.setattr(telegram_portfolio, "wrap_reply", fake_reply)
    refresh = lambda: {
            "success": True,
            "holdings_count": 3,
            "cash_count": 1,
            "accounts_count": 2,
            "error": None,
            "last_updated": "2026-06-26T01:02:03+00:00",
        }

    class Update:
        pass

    class Context:
        user_data = {}

    handler = telegram_portfolio.PortfolioCommandHandler(
        _portfolio_dependencies(refresh_gsheet_cache=refresh)
    )
    asyncio.run(handler.cmd_gsheet(Update(), Context()))

    assert len(replies) == 1
    assert "GSheet cache updated" in replies[0]
    assert "Holdings: 3" in replies[0]


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


def test_ticker_detail_hides_current_price_source(monkeypatch):
    handler = telegram_portfolio.PortfolioCommandHandler(
        _portfolio_dependencies(
            market_reader=SimpleNamespace(
                get_current_price=lambda _ticker: 100.0,
                fetch_price=lambda _ticker: 0.0,
            )
        )
    )
    text = handler.format_ticker_detail(
        "AAPL",
        {
            "qty": 2,
            "total_investment": 150.0,
            "currency": "USD",
            "name": "Apple",
            "cur_price": 0,
        },
        {
            "current_weights": {"AAPL": 0.1},
            "targets": {"AAPL": 0.2},
        },
        )

    assert "<b>Cur Price:</b> $100.00" in text
    assert "(WS)" not in text
    assert "(API)" not in text
    assert "(Avg)" not in text


def test_ticker_not_in_portfolio_hides_current_price_source(monkeypatch):
    handler = telegram_portfolio.PortfolioCommandHandler(
        _portfolio_dependencies(
            market_reader=SimpleNamespace(
                get_current_price=lambda _ticker: 7460.0,
                fetch_price=lambda _ticker: 0.0,
            )
        )
    )
    text = handler.format_ticker_not_in_portfolio(
        "453850",
        {"targets": {"453850": 0}},
    )

    assert "<b>Cur Price:</b> $7,460.00" in text
    assert "(WebSocket)" not in text
    assert "(API)" not in text
