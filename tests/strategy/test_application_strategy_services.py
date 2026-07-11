import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from application.order_report_service import OrderReportService
from application.strategy_run_service import StrategyRunService
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
    assert service.run_rebalancing(execute=False) == {"status": "skipped"}
    assert calls == [
        ("raoeo", {"execute": False}),
        ("va", {"execute": True}),
        ("rebalancing", {"execute": False}),
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
