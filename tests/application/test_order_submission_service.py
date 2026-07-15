import pytest

from application.order_report_service import OrderReportService
from application.order_submission_service import DurableOrderSubmissionService
from domain.strategy.base import OrderSide, StrategyOrder


def _order() -> StrategyOrder:
    return StrategyOrder("TQQQ", OrderSide.BUY, 1, 100.0)


def test_submission_persists_intent_before_broker_call():
    order = _order()
    calls = []
    service = DurableOrderSubmissionService(
        OrderReportService(
            execute_order=lambda received: calls.append(("broker", received.correlation_id))
            or (True, "accepted")
        )
    )

    service.submit(
        [order],
        persist_intent=lambda orders: calls.append(("intent", orders[0].correlation_id)),
    )

    assert calls == [("intent", order.correlation_id), ("broker", order.correlation_id)]


def test_submission_does_not_call_broker_when_intent_save_fails():
    calls = []
    service = DurableOrderSubmissionService(
        OrderReportService(
            execute_order=lambda _order: calls.append("broker") or (True, "accepted")
        )
    )

    with pytest.raises(RuntimeError, match="history unavailable"):
        service.submit(
            [_order()],
            persist_intent=lambda _orders: (_ for _ in ()).throw(
                RuntimeError("history unavailable")
            ),
        )

    assert calls == []


def test_submission_propagates_outcome_save_failure_after_one_broker_call():
    calls = []
    service = DurableOrderSubmissionService(
        OrderReportService(
            execute_order=lambda _order: calls.append("broker") or (True, "accepted")
        )
    )

    with pytest.raises(RuntimeError, match="outcome unavailable"):
        service.submit(
            [_order()],
            persist_intent=lambda _orders: calls.append("intent"),
            persist_outcome=lambda _results: (_ for _ in ()).throw(
                RuntimeError("outcome unavailable")
            ),
        )

    assert calls == ["intent", "broker"]
