import sys
import types
from pathlib import Path
import importlib.util

import pandas as pd

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC_DIR))


def _load_event_handler(monkeypatch):
    fake_kis = types.ModuleType("kis")
    fake_event_pipe = types.ModuleType("core.event_pipe")
    fake_event_pipe.print_viewer = lambda *args, **kwargs: None
    fake_ws_parser = types.ModuleType("kis.ws_parser")
    fake_ws_parser.mask_dict_for_log = lambda value: value
    fake_kis.ws_parser = fake_ws_parser
    fake_broker = types.ModuleType("broker")
    fake_order_admin = types.ModuleType("broker.order_admin")
    fake_order_admin.sync_open_orders = lambda: None
    fake_telegram_bot = types.ModuleType("telegram_bot")
    fake_telegram_utils = types.ModuleType("telegram_bot.telegram_utils")
    fake_telegram_utils.send_notification = lambda *args, **kwargs: None

    monkeypatch.setitem(sys.modules, "kis", fake_kis)
    monkeypatch.setitem(sys.modules, "core.event_pipe", fake_event_pipe)
    monkeypatch.setitem(sys.modules, "kis.ws_parser", fake_ws_parser)
    monkeypatch.setitem(sys.modules, "broker", fake_broker)
    monkeypatch.setitem(sys.modules, "broker.order_admin", fake_order_admin)
    monkeypatch.setitem(sys.modules, "telegram_bot", fake_telegram_bot)
    monkeypatch.setitem(sys.modules, "telegram_bot.telegram_utils", fake_telegram_utils)

    spec = importlib.util.spec_from_file_location(
        "event_handler_under_test",
        SRC_DIR / "broker" / "kis_event_handler.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_domestic_tick_logs_from_websocket_row(monkeypatch):
    event_handler = _load_event_handler(monkeypatch)
    messages = []

    monkeypatch.setattr(
        event_handler.trading_config,
        "get_stock_info",
        lambda code: {"name": "Samsung"} if code == "005930" else None,
    )
    monkeypatch.setattr(
        event_handler,
        "print_viewer",
        lambda category, level, message: messages.append((category, level, message)),
    )

    row = pd.Series(
        {
            "MKSC_SHRN_ISCD": "005930",
            "STCK_CNTG_HOUR": "091500",
            "STCK_PRPR": "70000",
            "CNTG_VOL": "12",
            "PRDY_VRSS": "100",
            "PRDY_CTRT": "0.14",
            "PRDY_VRSS_SIGN": "2",
        }
    )

    assert event_handler._handle_domestic_market("H0UNCNT0", row) is True

    assert len(messages) == 1
    assert messages[0][0] == "MKT"
    assert messages[0][1] == "INFO"
    assert "005930" in messages[0][2]
    assert "70,000" in messages[0][2]


import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def test_kis_logger_logs_response_headers_and_body(caplog):
    from broker.kis_logger import wrap_http_request_for_kis_logging

    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse(
            500,
            {"tr_id": "TTTC8434R", "authorization": "secret"},
            '{"rt_cd":"1","msg_cd":"EGW00201","msg1":"초당 거래건수를 초과하였습니다."}',
        )

    wrapped = wrap_http_request_for_kis_logging(fake_request)

    with caplog.at_level(logging.DEBUG):
        response = wrapped(
            "GET",
            "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/trading/inquire-balance",
            headers={"authorization": "Bearer token", "appkey": "app-key"},
            params={"CANO": "12345678", "ACNT_PRDT_CD": "01"},
        )

    assert response.status_code == 500
    assert calls[0][0] == "GET"
    log_text = caplog.text
    assert "[KISAPI] response" in log_text
    assert "EGW00201" in log_text
    assert "초당 거래건수를 초과하였습니다." in log_text
    assert "tr_id" in log_text
    assert "secret" not in log_text
    assert "Bearer token" not in log_text
    assert "app-key" not in log_text
    assert "12345678" not in log_text


def test_kis_logger_masks_json_string_payloads(caplog):
    from broker.kis_logger import wrap_http_request_for_kis_logging

    def fake_request(method, url, **kwargs):
        return FakeResponse(
            200,
            {},
            '{"ctx_area_fk100":"12345678^01^cursor","rt_cd":"0"}',
        )

    wrapped = wrap_http_request_for_kis_logging(fake_request)

    with caplog.at_level(logging.DEBUG):
        wrapped(
            "POST",
            "https://openapi.koreainvestment.com:9443/oauth2/Approval",
            data='{"appkey":"app-key","secretkey":"secret-key"}',
        )

    log_text = caplog.text
    assert "app-key" not in log_text
    assert "secret-key" not in log_text
    assert "12345678" not in log_text
    assert "'appkey': '***'" in log_text
    assert "'ctx_area_fk100': '***'" in log_text


def test_sanitize_for_log_masks_existing_kis_sensitive_shapes():
    from broker.kis_logger import sanitize_for_log

    payload = {
        "authorization": "Bearer token",
        "my_hts_id": "hts-id",
        "tr_key": "real-key",
        "approval_key": "approval",
        "body": {
            "input": {
                "CANO": "12345678",
                "ACNT_PRDT_CD": "01",
                "ctx_area_fk100": "12345678^01^cursor",
                "STCK_SHRN_ISCD": "SOXL",
            }
        },
    }

    assert sanitize_for_log(payload) == {
        "authorization": "***",
        "my_hts_id": "***",
        "tr_key": "***",
        "approval_key": "***",
        "body": {
            "input": {
                "CANO": "***",
                "ACNT_PRDT_CD": "***",
                "ctx_area_fk100": "***",
                "STCK_SHRN_ISCD": "SOXL",
            }
        },
    }


def test_kis_logger_logs_websocket_send_with_sanitized_payload(caplog):
    from broker.kis_logger import log_ws_send

    message = {
        "header": {"approval_key": "approval"},
        "body": {"input": {"tr_id": "H0STCNI0", "tr_key": "real-key"}},
    }

    with caplog.at_level(logging.INFO):
        log_ws_send(message)

    log_text = caplog.text
    assert "send message >>" in log_text
    assert '"approval_key": "***"' in log_text
    assert "real-key" not in log_text
    assert "H0STCNI0" in log_text


class FakeResponse:
    def __init__(self, status_code, headers, text):
        self.status_code = status_code
        self.headers = headers
        self.text = text

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC_DIR))

from kis.ws_parser import (
    build_schema_drift_alert,
    mask_dict_for_log,
    mask_record_for_log,
    normalize_record,
    should_send_schema_drift_alert,
    should_log_normalization,
    split_records,
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


def test_split_records_keeps_single_record_extra_fields_together():
    records = split_records(["a", "b", "c"], count=1, real_size=2)

    assert records == [["a", "b", "c"]]


def test_split_records_chunks_multiple_records_and_skips_incomplete_tail():
    records = split_records(["a", "b", "c", "d", "tail"], count=2, real_size=2)

    assert records == [["a", "b"], ["c", "d"]]


def test_mask_record_for_log_preserves_positions_and_masks_sensitive_fields():
    record = ["cust", "acct", "order", "ticker", "10"]
    columns = ["CUST_ID", "ACNT_NO", "ODER_NO", "STCK_SHRN_ISCD", "CNTG_QTY"]

    masked = mask_record_for_log(record, columns)

    assert masked == ["********", "********", "********", "ticker", "10"]


def test_mask_dict_for_log_masks_sensitive_fields():
    data = {
        "CUST_ID": "customer",
        "ACNT_NO": "account",
        "ODER_NO": "order",
        "ACNT_NAME": "name",
        "STCK_SHRN_ISCD": "SOXL",
    }

    masked = mask_dict_for_log(data)

    assert masked == {
        "CUST_ID": "********",
        "ACNT_NO": "********",
        "ODER_NO": "********",
        "ACNT_NAME": "********",
        "STCK_SHRN_ISCD": "SOXL",
    }


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
        field_count=24,
        column_count=25,
    )

    assert "KIS WebSocket schema drift" in alert
    assert "TR: H0GSCNI0" in alert
    assert "fields=24 columns=25" in alert
    assert "record=" not in alert
