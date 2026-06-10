import importlib.util
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"

spec = importlib.util.spec_from_file_location(
    "ws_notifications_under_test",
    SRC_DIR / "broker" / "kis_ws_notifications.py",
)
ws_notifications = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ws_notifications)

build_reconnection_failure_message = (
    ws_notifications.build_reconnection_failure_message
)
build_reconnection_success_message = (
    ws_notifications.build_reconnection_success_message
)
should_notify_reconnection_failure = (
    ws_notifications.should_notify_reconnection_failure
)
should_notify_reconnection_success = (
    ws_notifications.should_notify_reconnection_success
)


def test_reconnection_failure_notifications_start_on_third_failure():
    assert should_notify_reconnection_failure(1) is False
    assert should_notify_reconnection_failure(2) is False
    assert should_notify_reconnection_failure(3) is True
    assert should_notify_reconnection_failure(4) is True


def test_reconnection_success_notifications_only_after_reported_outage():
    assert should_notify_reconnection_success(1) is False
    assert should_notify_reconnection_success(2) is False
    assert should_notify_reconnection_success(3) is True
    assert should_notify_reconnection_success(4) is True


def test_reconnection_messages_include_attempt_context():
    failure_message = build_reconnection_failure_message(3, "closed")
    success_message = build_reconnection_success_message(3)

    assert "Attempt 3 failed." in failure_message
    assert "Error: closed" in failure_message
    assert "3 failed attempt(s)" in success_message
