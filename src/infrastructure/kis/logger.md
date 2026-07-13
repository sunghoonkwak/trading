# KIS Logging Helpers (`src/infrastructure/kis/logger.py`)

This infrastructure helper installs KIS-only HTTP logging on top of the shared
`requests` timeout wrapper. It logs KIS REST and WebSocket diagnostic data
without exposing credentials, account numbers, order numbers, or token fields.

- `install_kis_logging()` wraps `requests.api.request` once.
- `wrap_http_request_for_kis_logging()` is the testable wrapper seam.
- `sanitize_for_log()`, `log_api_request_debug()`, `log_api_resp_debug()`, and
  `log_ws_send()` redact sensitive mappings and JSON payloads before logging.
