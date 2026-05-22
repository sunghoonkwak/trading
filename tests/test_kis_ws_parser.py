import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from kis.ws_parser import (
    build_schema_drift_alert,
    mask_record_for_log,
    normalize_record,
    should_send_schema_drift_alert,
    should_log_normalization,
)


def test_normalize_record_pads_missing_trailing_fields():
    record, note = normalize_record(["a", "b"], ["A", "B", "C"])

    assert record == ["a", "b", ""]
    assert "padded 1 missing field" in note
    assert "C" in note


def test_normalize_record_truncates_extra_fields():
    record, note = normalize_record(["a", "b", "c"], ["A", "B"])

    assert record == ["a", "b"]
    assert note == "truncated 1 extra field(s)"


def test_mask_record_for_log_preserves_positions_and_masks_sensitive_fields():
    record = ["cust", "acct", "order", "ticker", "10"]
    columns = ["CUST_ID", "ACNT_NO", "ODER_NO", "STCK_SHRN_ISCD", "CNTG_QTY"]

    masked = mask_record_for_log(record, columns)

    assert masked == ["********", "********", "********", "ticker", "10"]


def test_should_not_log_expected_compatibility_truncation():
    assert should_log_normalization("truncated 54 extra field(s)", True) is False


def test_should_log_padding_even_with_compatibility_fix():
    assert should_log_normalization("padded 1 missing field(s): ['CNTG_UNPR12']", True) is True


def test_should_rate_limit_schema_drift_alerts_by_tr_id():
    sent_at = {}

    assert should_send_schema_drift_alert(sent_at, "H0GSCNI0", now=100.0) is True
    assert should_send_schema_drift_alert(sent_at, "H0GSCNI0", now=200.0) is False
    assert should_send_schema_drift_alert(sent_at, "H0GSCNI0", now=3701.0) is True


def test_build_schema_drift_alert_has_summary_without_raw_record():
    alert = build_schema_drift_alert(
        "H0GSCNI0",
        "padded 1 missing field(s): ['CNTG_UNPR12']",
        raw_count=24,
        column_count=25,
    )

    assert "KIS WebSocket schema drift" in alert
    assert "TR: H0GSCNI0" in alert
    assert "raw=24 columns=25" in alert
    assert "record=" not in alert
