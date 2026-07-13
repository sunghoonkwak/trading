# Toss HTTP Client (`src/infrastructure/toss/client.py`)

`request_json()` is the common Toss transport boundary. It applies the supplied
timeout, rate-limit group, retry policy for HTTP 429 only, response parsing,
and redacted request/response logging. Other HTTP and transport errors raise a
sanitized `RuntimeError` and may invoke the injected best-effort notifier.

`configure_failure_notifier()` installs that notifier from the composition
root; this client never imports a Telegram interface.
