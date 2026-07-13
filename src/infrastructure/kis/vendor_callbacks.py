"""Application-owned collaborators registered with the isolated KIS vendor API."""

import logging
from typing import Any, Callable, Optional

from infrastructure.kis.kis_logger import (
    log_api_request_debug,
    log_api_resp_debug,
    log_ws_send,
)
from infrastructure.kis.kis_ws_notifications import (
    build_reconnection_failure_message,
    build_reconnection_success_message,
)

_notification_sender = None
_credential_provider: Optional[Callable[[], tuple[str | None, str | None, str | None]]] = None
_alert_publisher: Optional[Callable[[str, str], None]] = None
_websocket_state_publisher: Optional[Callable[[str], None]] = None


def configure_runtime_collaborators(
    *,
    credential_provider: Optional[Callable[[], tuple[str | None, str | None, str | None]]],
    alert_publisher: Optional[Callable[[str, str], None]],
    websocket_state_publisher: Optional[Callable[[str], None]],
) -> None:
    """Inject runtime-only KIS collaborators at composition time."""
    global _credential_provider, _alert_publisher, _websocket_state_publisher
    _credential_provider = credential_provider
    _alert_publisher = alert_publisher
    _websocket_state_publisher = websocket_state_publisher


def configure_notification_sender(sender) -> None:
    """Inject notification delivery from the runtime composition root."""
    global _notification_sender
    _notification_sender = sender


def _send_notification(message: str, *, parse_mode: str = "HTML") -> None:
    if _notification_sender is not None:
        _notification_sender(message, parse_mode=parse_mode)


def _publish_alert(message: str, level: str) -> None:
    if _alert_publisher is None:
        return
    try:
        _alert_publisher(message, level)
    except Exception as error:
        logging.warning("[KIS] Alert publication failed: %s", error)


def _publish_websocket_state(status: str) -> None:
    if _websocket_state_publisher is None:
        return
    try:
        _websocket_state_publisher(status)
    except Exception as error:
        logging.warning("[KIS] WebSocket state publication failed: %s", error)


def _handle_websocket_event(event: str, **payload: Any) -> None:
    if event == "alert":
        message = str(payload["message"])
        _publish_alert(f"[WS] {message.split(chr(10))[0][:60]}", payload["level"])
    elif event == "notification":
        _send_notification(str(payload["message"]), parse_mode="HTML")
    elif event == "status":
        _publish_websocket_state(str(payload["status"]))
    elif event == "reconnection_success":
        _send_notification(
            build_reconnection_success_message(int(payload["failed_attempts"])),
            parse_mode="HTML",
        )
    elif event == "reconnection_failure":
        _send_notification(
            build_reconnection_failure_message(
                int(payload["attempt_number"]), payload["error"]
            ),
            parse_mode="HTML",
        )
    elif event == "approval_refresh_failure":
        _send_notification(
            "🔑 <b>Approval Key Refresh Failed</b>\n"
            f"Error: {payload['error']}\n"
            "Manual intervention may be required.",
            parse_mode="HTML",
        )


def configure_kis_vendor_hooks() -> None:
    """Inject host behavior after startup dependencies are ready."""
    from infrastructure.kis.kis_api import kis_auth

    kis_auth.configure_hooks(
        credential_provider=_credential_provider,
        api_request_logger=log_api_request_debug,
        api_response_logger=log_api_resp_debug,
        websocket_send_logger=log_ws_send,
        critical_error_handler=lambda message: _publish_alert(message, "ERROR"),
        websocket_event_handler=_handle_websocket_event,
    )
    logging.debug("Configured KIS vendor callbacks")
