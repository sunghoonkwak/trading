import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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

    with caplog.at_level(logging.INFO):
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

    with caplog.at_level(logging.INFO):
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


def test_kis_logger_ignores_non_kis_urls(caplog):
    from broker.kis_logger import wrap_http_request_for_kis_logging

    def fake_request(method, url, **kwargs):
        return FakeResponse(200, {}, '{"ok": true}')

    wrapped = wrap_http_request_for_kis_logging(fake_request)

    with caplog.at_level(logging.INFO):
        wrapped("GET", "https://example.test/api")

    assert "[KISAPI]" not in caplog.text


class FakeResponse:
    def __init__(self, status_code, headers, text):
        self.status_code = status_code
        self.headers = headers
        self.text = text
