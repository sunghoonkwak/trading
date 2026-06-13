from __future__ import annotations

import json
import logging
from typing import Callable, Mapping
from urllib import error

from toss.rate_limit import DEFAULT_RATE_LIMIT_MANAGER, TossRateLimitManager


def request_json(
    api_request,
    *,
    group: str,
    action_name: str,
    timeout: float,
    urlopen: Callable[..., object],
    rate_limiter: TossRateLimitManager = DEFAULT_RATE_LIMIT_MANAGER,
    max_retries: int = 3,
    notify_func: Callable[[str], None] | None = None,
) -> dict[str, object]:
    attempt = 0
    while True:
        rate_limiter.wait(group)
        _log_request(api_request, group, action_name, attempt)
        try:
            with urlopen(api_request, timeout=timeout) as response:
                raw_body = response.read().decode("utf-8")
                payload = json.loads(raw_body)
                headers = getattr(response, "headers", {})
                rate_limiter.update_from_headers(group, headers)
                status = int(getattr(response, "status", 200))
                _log_response(group, action_name, status, headers, payload)
                return payload
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            headers = getattr(exc, "headers", {})
            rate_limiter.update_from_headers(group, headers)
            _log_response(group, action_name, exc.code, headers, details)
            if exc.code != 429 or attempt >= max_retries:
                message = (
                    f"Toss {action_name} request failed: HTTP {exc.code} {details}"
                )
                _send_failure_notification(
                    group=group,
                    action_name=action_name,
                    message=message,
                    notify_func=notify_func,
                )
                raise RuntimeError(message) from exc

            delay = rate_limiter.retry_delay(headers, attempt)
            logging.info(
                "[TossAPI] rate limited group=%s action=%s retry_after=%.3fs attempt=%s/%s",
                group,
                action_name,
                delay,
                attempt + 1,
                max_retries,
            )
            rate_limiter.sleep(delay)
            attempt += 1
        except error.URLError as exc:
            logging.info(
                "[TossAPI] transport_error group=%s action=%s reason=%s",
                group,
                action_name,
                exc.reason,
            )
            message = f"Toss {action_name} request failed: {exc.reason}"
            _send_failure_notification(
                group=group,
                action_name=action_name,
                message=message,
                notify_func=notify_func,
            )
            raise RuntimeError(message) from exc


def _send_failure_notification(
    *,
    group: str,
    action_name: str,
    message: str,
    notify_func: Callable[[str], None] | None,
) -> None:
    try:
        sender = notify_func
        if sender is None:
            from telegram_bot.telegram_utils import send_notification

            sender = send_notification
        sender(
            "<b>Toss API query failed</b>\n"
            f"Group: {group}\n"
            f"Action: {action_name}\n"
            f"{message}"
        )
    except Exception as exc:
        logging.warning("[TossAPI] failed to send query failure notification: %s", exc)


def _log_request(api_request, group: str, action_name: str, attempt: int) -> None:
    body = getattr(api_request, "data", None)
    logging.info(
        "[TossAPI] request group=%s action=%s attempt=%s method=%s url=%s headers=%s body=%s",
        group,
        action_name,
        attempt + 1,
        getattr(api_request, "method", None) or api_request.get_method(),
        api_request.full_url,
        _sanitize_headers(dict(api_request.header_items())),
        _sanitize_body(body),
    )


def _log_response(
    group: str,
    action_name: str,
    status: int,
    headers: Mapping[str, object],
    payload: object,
) -> None:
    logging.info(
        "[TossAPI] response group=%s action=%s status=%s rate_limit=%s body=%s",
        group,
        action_name,
        status,
        _rate_limit_headers(headers),
        _sanitize_payload(payload),
    )


def _sanitize_headers(headers: Mapping[str, object]) -> dict[str, object]:
    sanitized = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered == "authorization":
            sanitized[key] = "Bearer ***"
        elif lowered == "x-tossinvest-account":
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


def _rate_limit_headers(headers: Mapping[str, object]) -> dict[str, object]:
    names = (
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After",
    )
    return {name: headers.get(name) for name in names if headers.get(name) is not None}


def _sanitize_body(body: object) -> object:
    if body is None:
        return None
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    try:
        return _sanitize_payload(json.loads(str(body)))
    except json.JSONDecodeError:
        return "<form-body>"


def _sanitize_payload(payload: object) -> object:
    if isinstance(payload, str):
        return payload[:1000]
    if isinstance(payload, dict):
        return {
            key: _masked_value(key, value)
            for key, value in list(payload.items())[:50]
        }
    if isinstance(payload, list):
        return [_sanitize_payload(item) for item in payload[:10]]
    return payload


def _masked_value(key: object, value: object) -> object:
    lowered = str(key).lower()
    if lowered in {
        "access_token",
        "refresh_token",
        "client_secret",
        "accountno",
        "accountseq",
    }:
        return "***"
    return _sanitize_payload(value)
