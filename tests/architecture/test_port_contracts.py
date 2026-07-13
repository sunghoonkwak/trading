import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from application.ports import (
    CorrelationId,
    MarketPriceReader,
    OpenOrderReader,
    OperationResult,
    PortfolioReader,
    PortfolioSource,
    SerializedKisOperations,
    StrategyOrderExecutor,
    redact_value,
)


def test_port_result_preserves_safe_outcome_and_correlation_contract():
    result = OperationResult(value={"status": "accepted"}, correlation_id=CorrelationId("c-1"))

    assert result.success is True
    assert result.ambiguous is False
    assert result.correlation_id == "c-1"


def test_port_redaction_masks_credentials_and_account_values_recursively():
    payload = {
        "authorization": "Bearer secret-token",
        "account_number": "12345678",
        "nested": {"app_key": "key", "symbol": "SOXL"},
    }

    assert redact_value(payload) == {
        "authorization": "***",
        "account_number": "***",
        "nested": {"app_key": "***", "symbol": "SOXL"},
    }


def test_portfolio_source_contract_requires_only_normalized_fetch():
    class FakeSource:
        def fetch(self, *, scope):
            return {"metadata": {}, "scope": scope}

    source: PortfolioSource = FakeSource()
    assert source.fetch(scope="all") == {"metadata": {}, "scope": "all"}


def test_serialized_kis_operations_preserve_correlation_and_safe_failure():
    class FakeOperations:
        def execute(self, operation, *, timeout=30.0, correlation_id=None):
            assert timeout == 1.0
            assert correlation_id == "portfolio-1"
            return OperationResult(
                error="KIS operation timed out",
                correlation_id=CorrelationId("portfolio-1"),
            )

    operations: SerializedKisOperations = FakeOperations()
    result = operations.execute(
        lambda: {"account": "secret"},
        timeout=1.0,
        correlation_id=CorrelationId("portfolio-1"),
    )

    assert result.success is False
    assert result.error == "KIS operation timed out"
    assert result.correlation_id == "portfolio-1"


def test_portfolio_reader_contract_accepts_the_application_service():
    class Reader:
        def get_portfolio_data(self, force_refresh=False, scope="all"):
            return {"force_refresh": force_refresh, "scope": scope}

    reader: PortfolioReader = Reader()
    assert reader.get_portfolio_data(force_refresh=True, scope="toss") == {
        "force_refresh": True,
        "scope": "toss",
    }


def test_order_executor_contract_accepts_a_broker_adapter():
    class Executor:
        def execute(self, order):
            return (order, "accepted")

    executor: StrategyOrderExecutor = Executor()
    assert executor.execute("SOXL") == ("SOXL", "accepted")


def test_market_and_open_order_reader_contracts_accept_adapters():
    class Market:
        def get_current_price(self, _ticker):
            return 10.0

        def fetch_price(self, _ticker):
            return 11.0

    class Orders:
        def fetch_open_orders(self):
            return (None, 1, 2, 3)

    market: MarketPriceReader = Market()
    orders: OpenOrderReader = Orders()
    assert (market.get_current_price("SOXL"), market.fetch_price("SOXL")) == (10.0, 11.0)
    assert orders.fetch_open_orders() == (None, 1, 2, 3)
