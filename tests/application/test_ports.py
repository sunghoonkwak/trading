from application.ports import CorrelationId, OperationResult, redact_value


def test_operation_result_preserves_safe_outcome_and_correlation():
    result = OperationResult(value={"status": "accepted"}, correlation_id=CorrelationId("c-1"))

    assert result.success is True
    assert result.ambiguous is False
    assert result.correlation_id == "c-1"


def test_redaction_masks_credentials_and_account_values_recursively():
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
