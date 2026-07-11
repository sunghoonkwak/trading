import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from application.order_report_service import OrderReportService
from application.strategy_run_service import StrategyMarketDataService, StrategyRunService
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


def test_order_report_service_returns_channel_neutral_execution_result():
    order = StrategyOrder("SOXL", OrderSide.BUY, 1, 10.0)
    service = OrderReportService(execute_order=lambda received: (received is order, "accepted"))

    assert service.execute(order) == {
        "order": order,
        "success": True,
        "message": "accepted",
    }


def test_legacy_execution_service_exposes_application_use_case_facade(monkeypatch):
    from strategy import execution_service

    monkeypatch.setattr(execution_service, "run_raoeo_strategy", lambda **_kwargs: {"strategy": "raoeo"})
    service = execution_service.get_strategy_run_service()

    assert service.run_raoeo() == {"strategy": "raoeo"}


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
