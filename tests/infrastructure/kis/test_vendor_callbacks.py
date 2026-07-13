import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from infrastructure.kis.kis_api import kis_auth


def test_vendor_websocket_events_use_registered_callbacks_without_host_imports(monkeypatch):
    events = []
    monkeypatch.setattr(kis_auth, "_websocket_event_handler", None)
    kis_auth.configure_hooks(websocket_event_handler=lambda event, **data: events.append((event, data)))

    websocket = kis_auth.KISWebSocket(api_url="")
    websocket._add_alert("Connected", "SUCCESS")
    websocket._update_ws_status("connected")
    websocket._send_telegram_notification("masked notification")

    assert events == [
        ("alert", {"message": "Connected", "level": "SUCCESS"}),
        ("status", {"status": "connected"}),
        ("notification", {"message": "masked notification"}),
    ]


def test_vendor_hooks_are_optional_for_standalone_imports(monkeypatch):
    monkeypatch.setattr(kis_auth, "_websocket_event_handler", None)
    websocket = kis_auth.KISWebSocket(api_url="")

    websocket._add_alert("No host configured")
    websocket._update_ws_status("disconnected")
    websocket._send_telegram_notification("No host configured")


def test_vendor_callbacks_publish_alerts_and_state_through_adapters():
    from infrastructure.kis import vendor_callbacks

    alerts = []
    states = []
    vendor_callbacks.configure_runtime_collaborators(
        credential_provider=lambda: ("app-key", "app-secret", "hts-id"),
        alert_publisher=lambda message, level: alerts.append((message, level)),
        websocket_state_publisher=states.append,
    )

    vendor_callbacks._handle_websocket_event(
        "alert",
        message="Connected\nprivate detail",
        level="SUCCESS",
    )
    vendor_callbacks._handle_websocket_event("status", status="connected")

    assert alerts == [("[WS] Connected", "SUCCESS")]
    assert states == ["connected"]
