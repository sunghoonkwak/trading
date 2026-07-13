import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from application.order_report_service import OrderManagementService, OrderReportService
from application.strategy_execution import (
    StrategyExecutionDependencies,
    StrategyExecutionRuntime,
)
from application.strategy_run_service import (
    StrategyHistoryService,
    StrategyMarketDataService,
    StrategyRunService,
)
from domain.strategy.base import OrderSide, StrategyOrder


def test_strategy_run_service_delegates_each_use_case_to_injected_port():
    calls = []
    service = StrategyRunService(
        run_raoeo=lambda **kwargs: calls.append(("raoeo", kwargs)) or {"status": "skipped"},
        run_value_averaging=lambda **kwargs: calls.append(("va", kwargs)) or {"status": "skipped"},
        run_rebalancing=lambda **kwargs: calls.append(("rebalancing", kwargs)) or {"status": "skipped"},
    )

    assert service.run_raoeo(execute=False) == {"status": "skipped"}
    assert service.run_value_averaging(execute=True) == {"status": "skipped"}
    assert service.run_rebalancing(execute=False, orderable_cache_key="2026-07-11") == {"status": "skipped"}
    assert calls == [
        ("raoeo", {"execute": False}),
        ("va", {"execute": True}),
        ("rebalancing", {"execute": False, "orderable_cache_key": "2026-07-11"}),
    ]


def test_strategy_run_service_delegates_the_shared_strategy_suite():
    service = StrategyRunService(
        run_raoeo=lambda **_kwargs: {},
        run_value_averaging=lambda **_kwargs: {},
        run_rebalancing=lambda **_kwargs: {},
        run_suite=lambda **kwargs: ({"raoeo": kwargs}, {"va": kwargs}),
    )

    assert service.run_suite(execute=True) == (
        {"raoeo": {"execute": True}},
        {"va": {"execute": True}},
    )


def test_order_report_service_returns_channel_neutral_execution_result():
    order = StrategyOrder("SOXL", OrderSide.BUY, 1, 10.0)
    service = OrderReportService(execute_order=lambda received: (received is order, "accepted"))

    result = service.execute(order)

    assert result["order"] is order
    assert result["success"] is True
    assert result["message"] == "accepted"
    assert result["ambiguous"] is False
    assert result["correlation_id"] == order.correlation_id


def test_order_report_service_executes_sells_before_buys_and_waits_once():
    sell = StrategyOrder("BIL", OrderSide.SELL, 1, 100.0)
    buy = StrategyOrder("SOXL", OrderSide.BUY, 1, 10.0)
    calls = []
    service = OrderReportService(
        execute_order=lambda order: calls.append(order.symbol) or (True, "accepted"),
        sleep=lambda seconds: calls.append(("sleep", seconds)),
    )

    results = service.execute_many([buy, sell], sell_first=True, sell_wait_seconds=5)

    assert calls == ["BIL", ("sleep", 5), "SOXL"]
    assert [result["order"] for result in results] == [sell, buy]


def test_order_report_service_returns_retry_status_and_pending_orders():
    first = StrategyOrder("SOXL", OrderSide.BUY, 1, 10.0)
    second = StrategyOrder("TQQQ", OrderSide.BUY, 1, 20.0)
    service = OrderReportService(
        execute_order=lambda order: (order is first, "accepted" if order is first else "rejected")
    )

    result = service.retry_failed([first, second])

    assert result["status"].value == "partial"
    assert result["succeeded_orders"] == [first]
    assert result["pending_orders"] == [second]


def test_order_report_service_assigns_correlation_id_to_ambiguous_outcome():
    order = StrategyOrder("SOXL", OrderSide.BUY, 1, 10.0)
    service = OrderReportService(
        execute_order=lambda _order: (False, "[AMBIGUOUS] broker timeout")
    )

    result = service.execute(order)

    assert result["ambiguous"] is True
    assert result["correlation_id"]
    assert order.correlation_id == result["correlation_id"]


def test_order_report_service_reconciles_ambiguous_order_without_resubmitting():
    order = StrategyOrder("SOXL", OrderSide.BUY, 1, 10.0)
    calls = []
    service = OrderReportService(
        execute_order=lambda received: calls.append(received) or (False, "[AMBIGUOUS] timeout"),
        reconcile_order=lambda correlation_id: calls.append(correlation_id) or True,
    )

    result = service.execute(order)

    assert result["success"] is True
    assert result["ambiguous"] is False
    assert result["reconciled"] is True
    assert calls == [order, order.correlation_id]


def test_order_management_service_delegates_control_operations():
    calls = []
    service = OrderManagementService(
        sync_open_orders=lambda: calls.append("sync") or True,
        fetch_open_orders=lambda: ("orders", 1, 2, 3),
        execute_manage_action=lambda *args: calls.append(args) or ("result", None),
    )

    assert service.sync_open_orders() is True
    assert service.fetch_open_orders() == ("orders", 1, 2, 3)
    assert service.execute_manage_action("TOSS", "2", {"id": "1"}, None) == (
        "result",
        None,
    )
    assert calls == ["sync", ("TOSS", "2", {"id": "1"}, None)]


def test_application_execution_exposes_application_use_case_facade(monkeypatch):
    from application import strategy_execution

    monkeypatch.setattr(strategy_execution, "run_raoeo_strategy", lambda **_kwargs: {"strategy": "raoeo"})
    service = strategy_execution.get_strategy_run_service()

    assert service.run_raoeo() == {"strategy": "raoeo"}


def test_runtime_runs_raoeo_from_its_own_dependencies():
    dependencies = StrategyExecutionDependencies(
        load_strategy_config=lambda: {"raoeo": {"enabled": False}},
        load_history=lambda: [],
        save_history=lambda _history: True,
        fetch_prices=lambda _tickers: {},
        strategy_broker_name=lambda: "kis",
        get_orderable_usd=lambda _symbol, _price: 0.0,
        execute_order=lambda _order: (True, "accepted"),
        portfolio_reader_factory=lambda: None,
        get_market_status=lambda _date: {"is_market_open": True, "message": "open"},
    )

    report = StrategyExecutionRuntime(dependencies).run_raoeo(execute=False)

    assert report["status"].value == "disabled"


def test_runtime_runs_value_averaging_from_its_own_dependencies():
    dependencies = StrategyExecutionDependencies(
        load_strategy_config=lambda: {"value_averaging": {"enabled": False}},
        load_history=lambda: [],
        save_history=lambda _history: True,
        fetch_prices=lambda _tickers: {},
        strategy_broker_name=lambda: "kis",
        get_orderable_usd=lambda _symbol, _price: 0.0,
        execute_order=lambda _order: (True, "accepted"),
        portfolio_reader_factory=lambda: None,
        get_market_status=lambda _date: {"is_market_open": True, "message": "open"},
    )

    report = StrategyExecutionRuntime(dependencies).run_value_averaging(execute=False)

    assert report["status"].value == "disabled"


def test_runtime_runs_rebalancing_from_its_own_dependencies():
    dependencies = StrategyExecutionDependencies(
        load_strategy_config=lambda: {"rebalancing": {"enabled": False}},
        load_history=lambda: [],
        save_history=lambda _history: True,
        fetch_prices=lambda _tickers: {},
        strategy_broker_name=lambda: "kis",
        get_orderable_usd=lambda _symbol, _price: 0.0,
        execute_order=lambda _order: (True, "accepted"),
        portfolio_reader_factory=lambda: None,
        get_market_status=lambda _date: {"is_market_open": True, "message": "open"},
    )

    report = StrategyExecutionRuntime(dependencies).run_rebalancing(execute=False)

    assert report["status"].value == "disabled"


def test_runtime_runs_strategy_suite_from_its_own_dependencies():
    dependencies = StrategyExecutionDependencies(
        load_strategy_config=lambda: {
            "raoeo": {"enabled": False},
            "value_averaging": {"enabled": False},
        },
        load_history=lambda: [],
        save_history=lambda _history: True,
        fetch_prices=lambda _tickers: {},
        strategy_broker_name=lambda: "kis",
        get_orderable_usd=lambda _symbol, _price: 0.0,
        execute_order=lambda _order: (True, "accepted"),
        portfolio_reader_factory=lambda: None,
        get_market_status=lambda _date: {"is_market_open": True, "message": "open"},
    )

    raoeo_report, va_report = StrategyExecutionRuntime(dependencies).run_suite()

    assert raoeo_report["status"].value == "disabled"
    assert va_report["status"].value == "disabled"


def test_market_data_service_uses_injected_portfolio_config_and_price_ports():
    requested = []
    service = StrategyMarketDataService(
        load_portfolio=lambda *, force_refresh, scope: requested.append(
            (force_refresh, scope)
        ) or {"merged_data": {"TQQQ": {"cur_price": 100.0}}},
        load_strategy_config=lambda: {"raoeo": {"targets": {"TQQQ": {}, "SOXL": {}}}},
        fetch_prices=lambda tickers: {ticker: 10.0 for ticker in tickers},
        resolve_price=lambda _ticker, holding, _prices: holding.get("cur_price", 0.0),
        strategy_broker_name=lambda: "toss",
    )

    holdings, prices = service.get_market_data(force_refresh=True)

    assert requested == [(True, "toss")]
    assert holdings == {"TQQQ": {"cur_price": 100.0}}
    assert prices == {"TQQQ": 100.0, "SOXL": 10.0}


def test_history_service_removes_only_the_requested_date_and_persists_it():
    saved = []
    service = StrategyHistoryService(
        load=lambda: [{"date": "2026-07-10"}, {"date": "2026-07-11"}],
        save=lambda history: saved.append(history) or True,
    )

    assert service.clear_date("2026-07-10") == {"date": "2026-07-10", "removed": True}
    assert saved == [[{"date": "2026-07-11"}]]


def test_history_service_upserts_strategy_and_preserves_cash_funding_results():
    saved = []
    service = StrategyHistoryService(
        load=lambda: [{"date": "2026-07-11", "raoeo": {"cash_funding_results": ["sale"]}}],
        save=lambda history: saved.append(history) or True,
    )

    service.save_strategy("2026-07-11", "raoeo", {"orders": []})

    assert saved == [[
        {"date": "2026-07-11", "raoeo": {"orders": [], "cash_funding_results": ["sale"]}}
    ]]
