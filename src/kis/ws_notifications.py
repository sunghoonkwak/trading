"""WebSocket reconnection notification policy."""

RECONNECTION_ALERT_THRESHOLD = 3


def should_notify_reconnection_failure(attempt_number: int) -> bool:
    """Return True once repeated reconnect failures need operator attention."""
    return attempt_number >= RECONNECTION_ALERT_THRESHOLD


def should_notify_reconnection_success(failed_attempts: int) -> bool:
    """Return True only after a reconnect outage was already reported."""
    return failed_attempts >= RECONNECTION_ALERT_THRESHOLD


def build_reconnection_failure_message(attempt_number: int, error: object) -> str:
    return (
        f"❌ <b>WebSocket Reconnection Failed</b>\n"
        f"Attempt {attempt_number} failed.\n"
        f"Error: {error}"
    )


def build_reconnection_success_message(failed_attempts: int) -> str:
    return (
        f"✅ <b>WebSocket Reconnected</b>\n"
        f"Successfully reconnected after {failed_attempts} failed attempt(s)."
    )
