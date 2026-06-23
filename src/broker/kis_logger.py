from __future__ import annotations

import functools
import json
import logging
from typing import Callable, Mapping

import requests


KIS_HOST_MARKERS = (
    "koreainvestment.com",
    "openapi.koreainvestment.com",
)

SENSITIVE_KEYS = {
    "authorization",
    "appkey",
    "appsecret",
    "secretkey",
    "approval_key",
    "personalseckey",
    "my_hts_id",
    "tr_key",
    "cano",
    "acnt_prdt_cd",
    "acnt_no",
    "cust_id",
    "oder_no",
    "acnt_name",
    "account",
    "accountno",
    "accountseq",
}

SENSITIVE_PREFIXES = (
    "ctx_area_",
)


def install_kis_logging() -> None:
    """Install KIS HTTP logging while preserving the timeout patch."""
    current_request = requests.api.request
    if getattr(current_request, "_kis_logging", False):
        return
    requests.api.request = wrap_http_request_for_kis_logging(current_request)


def wrap_http_request_for_kis_logging(request_func: Callable[..., object]) -> Callable[..., object]:
    @functools.wraps(request_func)
    def wrapper(method, url, **kwargs):
        response = request_func(method, url, **kwargs)
        if _is_kis_url(str(url)):
            _log_http_response(method, str(url), kwargs, response)
        return response

    wrapper._kis_logging = True
    return wrapper


def sanitize_for_log(value: object) -> object:
    return _sanitize_mapping(value)


def log_api_request_debug(
    *,
    url: str | None = None,
    tr_id: str | None = None,
    headers: Mapping[str, object] | None = None,
    body: object = None,
) -> None:
    if url is not None:
        logging.debug("< Sending Info >")
        logging.debug("URL: %s, TR: %s", url, tr_id)
    else:
        logging.debug("<Sending Info> TR: %s", tr_id)
    logging.debug("<header>\n%s", sanitize_for_log(headers or {}))
    if body is not None:
        logging.debug("<body>\n%s", sanitize_for_log(body))


def log_api_resp_debug(api_response) -> None:
    logging.debug("<Header>")
    header = api_response.getHeader()
    for field in header._fields:
        logging.debug("\t-%s: %s", field, sanitize_for_log({field: getattr(header, field)})[field])

    logging.debug("<Body>")
    body = api_response.getBody()
    for field in body._fields:
        logging.debug("\t-%s: %s", field, sanitize_for_log({field: getattr(body, field)})[field])


def log_ws_send(message: Mapping[str, object]) -> None:
    logging.info("send message >> %s", json.dumps(sanitize_for_log(message)))


def _is_kis_url(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in KIS_HOST_MARKERS)


def _log_http_response(method: str, url: str, kwargs: Mapping[str, object], response) -> None:
    logging.debug(
        "[KISAPI] response method=%s url=%s status=%s headers=%s request=%s body=%s",
        method,
        url,
        getattr(response, "status_code", None),
        sanitize_for_log(getattr(response, "headers", {})),
        sanitize_for_log(
            {
                "headers": kwargs.get("headers", {}),
                "params": kwargs.get("params", {}),
                "data": kwargs.get("data"),
                "json": kwargs.get("json"),
            }
        ),
        _sanitize_body(getattr(response, "text", "")),
    )


def _sanitize_mapping(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: _mask_if_sensitive(key, nested)
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_mapping(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _sanitize_body(text: object) -> object:
    if not isinstance(text, str):
        return text
    if not text:
        return ""
    return _sanitize_text(text)


def _mask_if_sensitive(key: object, value: object) -> object:
    if str(key).lower() in SENSITIVE_KEYS:
        return "***"
    if str(key).lower().startswith(SENSITIVE_PREFIXES):
        return "***"
    return _sanitize_mapping(value)


def _sanitize_text(text: str) -> object:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text[:1000]
    return _sanitize_mapping(payload)
