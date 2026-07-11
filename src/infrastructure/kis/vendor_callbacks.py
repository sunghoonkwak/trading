"""Application-owned collaborators registered with the isolated KIS vendor API."""

import logging
from typing import Any

from core import display
from core.credentials import get_secrets_from_password
from infrastructure.kis.kis_logger import (
    log_api_request_debug,
    log_api_resp_debug,
    log_ws_send,
)
from infrastructure.kis.kis_ws_notifications import (
    build_reconnection_failure_message,
    build_reconnection_success_message,
)
from state.system_state import WebSocketStatus, update_kis_state
from telegram_bot.telegram_utils import send_notification


def _handle_websocket_event(event: str, **payload: Any) -> None:
    if event == "alert":
        message = str(payload["message"])
        display.add_alert(f"[WS] {message.split(chr(10))[0][:60]}", payload["level"])
    elif event == "notification":
        send_notification(str(payload["message"]), parse_mode="HTML")
    elif event == "status":
        status_map = {
            "connected": WebSocketStatus.CONNECTED,
            "connecting": WebSocketStatus.CONNECTING,
            "reconnecting": WebSocketStatus.RECONNECTING,
            "disconnected": WebSocketStatus.DISCONNECTED,
            "error": WebSocketStatus.ERROR,
        }
        status = status_map.get(payload["status"])
        if status is not None:
            update_kis_state(ws_status=status)
    elif event == "reconnection_success":
        send_notification(
            build_reconnection_success_message(int(payload["failed_attempts"])),
            parse_mode="HTML",
        )
    elif event == "reconnection_failure":
        send_notification(
            build_reconnection_failure_message(
                int(payload["attempt_number"]), payload["error"]
            ),
            parse_mode="HTML",
        )
    elif event == "approval_refresh_failure":
        send_notification(
            "🔑 <b>Approval Key Refresh Failed</b>\n"
            f"Error: {payload['error']}\n"
            "Manual intervention may be required.",
            parse_mode="HTML",
        )


def configure_kis_vendor_hooks() -> None:
    """Inject host behavior after startup dependencies are ready."""
    from infrastructure.kis.kis_api import kis_auth

    kis_auth.configure_hooks(
        credential_provider=get_secrets_from_password,
        api_request_logger=log_api_request_debug,
        api_response_logger=log_api_resp_debug,
        websocket_send_logger=log_ws_send,
        critical_error_handler=lambda message: display.add_alert(message, "ERROR"),
        websocket_event_handler=_handle_websocket_event,
    )
    logging.debug("Configured KIS vendor callbacks")
