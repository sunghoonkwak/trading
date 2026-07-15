import sys
import threading
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from application.order_report_service import OrderManagementService, OrderReportService
from application.strategy_execution import (
    StrategyExecutionDependencies,
    StrategyExecutionRuntime,
)
from application.strategy_run_service import (
    StrategyHistoryPersistenceError,
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


def test_runtime_exposes_application_use_case_facade():
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

    service = StrategyExecutionRuntime(dependencies).strategy_run_service()

    assert service.run_raoeo()["status"].value == "disabled"


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


def test_runtime_prepares_cash_funding_from_its_own_dependencies():
    buy_order = StrategyOrder("TQQQ", OrderSide.BUY, 10, 100.0)
    dependencies = StrategyExecutionDependencies(
        load_strategy_config=lambda: {"cash_ticker": "BIL"},
        load_history=lambda: [],
        save_history=lambda _history: True,
        fetch_prices=lambda _tickers: {},
        strategy_broker_name=lambda: "kis",
        get_orderable_usd=lambda _symbol, _price: 100.0,
        execute_order=lambda _order: (True, "accepted"),
        portfolio_reader_factory=lambda: None,
        get_market_status=lambda _date: {"is_market_open": True, "message": "open"},
    )

    order, info = StrategyExecutionRuntime(dependencies).prepare_cash_funding({
        "pending_orders": [buy_order],
        "info": {
            "holdings": {"BIL": {"qty": 20, "cur_price": 100.0}},
            "current_prices": {"BIL": 100.0},
        },
    })

    assert info["required"] is True
    assert order.symbol == "BIL"


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


def test_history_service_rejects_a_failed_strategy_save():
    service = StrategyHistoryService(load=lambda: [], save=lambda _history: False)

    with pytest.raises(StrategyHistoryPersistenceError, match="strategy history"):
        service.save_strategy("2026-07-11", "raoeo", {"orders": []})


def _executable_raoeo_dependencies(history, save_history, execute_order):
    return StrategyExecutionDependencies(
        load_strategy_config=lambda: {
            "raoeo": {
                "enabled": True,
                "targets": {
                    "TQQQ": {
                        "enabled": True,
                        "seed": 1000,
                        "duration": 1,
                        "phase": [
                            {
                                "name": "initial",
                                "threshold": 1.0,
                                "buy": [{"type": "normal", "ratio": 1.0}],
                                "sell": [],
                            }
                        ],
                    }
                },
            }
        },
        load_history=lambda: deepcopy(history),
        save_history=save_history,
        fetch_prices=lambda _tickers: {"TQQQ": 100.0},
        strategy_broker_name=lambda: "kis",
        get_orderable_usd=lambda _symbol, _price: 0.0,
        execute_order=execute_order,
        portfolio_reader_factory=lambda: type(
            "Reader",
            (),
            {"get_portfolio_data": lambda _self, **_kwargs: {"merged_data": {}}},
        )(),
        get_market_status=lambda _date: {"is_market_open": True, "message": "open"},
    )


def test_runtime_persists_ambiguous_intent_before_submitting_order():
    history = []
    saved = []

    def save_history(value):
        history[:] = deepcopy(value)
        saved.append(deepcopy(value))
        return True

    def execute_order(_order):
        intent = saved[-1][0]["raoeo"]["orders"][0]
        assert intent["ambiguous"] is True
        assert intent["correlation_id"]
        return True, "accepted"

    report = StrategyExecutionRuntime(
        _executable_raoeo_dependencies(history, save_history, execute_order)
    ).run_raoeo(execute=True)

    assert report["status"].value == "executed"
    assert saved[0][0]["raoeo"]["orders"][0]["ambiguous"] is True
    assert saved[-1][0]["raoeo"]["orders"][0]["success"] is True


def test_runtime_does_not_submit_order_when_intent_cannot_be_saved():
    history = []
    calls = []
    runtime = StrategyExecutionRuntime(
        _executable_raoeo_dependencies(
            history,
            save_history=lambda _value: False,
            execute_order=lambda _order: calls.append("submitted") or (True, "accepted"),
        )
    )

    report = runtime.run_raoeo(execute=True)

    assert calls == []
    assert report["status"].value == "error"
    assert "Failed to save strategy history" in report["error"]


def test_runtime_blocks_retry_when_final_order_save_fails():
    history = []
    save_count = 0
    calls = []

    def save_history(value):
        nonlocal save_count
        save_count += 1
        if save_count == 2:
            return False
        history[:] = deepcopy(value)
        return True

    runtime = StrategyExecutionRuntime(
        _executable_raoeo_dependencies(
            history,
            save_history=save_history,
            execute_order=lambda _order: calls.append("submitted") or (True, "accepted"),
        )
    )

    first_report = runtime.run_raoeo(execute=True)
    second_report = runtime.run_raoeo(execute=True)

    assert first_report["status"].value == "error"
    assert second_report["status"].value == "error"
    assert "Ambiguous order outcome" in second_report["error"]
    assert calls == ["submitted"]


def test_runtime_serializes_overlapping_strategy_execution():
    history = []
    started = threading.Event()
    release = threading.Event()
    calls = []

    def save_history(value):
        history[:] = deepcopy(value)
        return True

    def execute_order(_order):
        calls.append("submitted")
        started.set()
        assert release.wait(timeout=1)
        return True, "accepted"

    runtime = StrategyExecutionRuntime(
        _executable_raoeo_dependencies(history, save_history, execute_order)
    )
    first = threading.Thread(target=lambda: runtime.run_raoeo(execute=True))
    second = threading.Thread(target=lambda: runtime.run_raoeo(execute=True))

    first.start()
    assert started.wait(timeout=1)
    second.start()
    release.set()
    first.join(timeout=1)
    second.join(timeout=1)

    assert not first.is_alive()
    assert not second.is_alive()
    assert calls == ["submitted"]
