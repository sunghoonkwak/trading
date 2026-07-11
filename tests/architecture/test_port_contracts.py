import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from application.ports import CorrelationId, OperationResult, PortfolioSource, redact_value


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
