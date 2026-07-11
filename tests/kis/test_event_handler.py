import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from broker import kis_event_handler


def test_on_result_reports_empty_frames_without_dispatching(monkeypatch):
    messages = []
    monkeypatch.setattr(
        kis_event_handler,
        "print_viewer",
        lambda *args: messages.append(args),
    )

    kis_event_handler.on_result(None, "H0STCNI0", pd.DataFrame(), {})

    assert messages == [("SYS", "ERROR", "System Message received for TR: H0STCNI0")]


def test_domestic_order_parse_error_has_no_notification_side_effect(monkeypatch):
    messages = []

    def unexpected_side_effect(*args, **kwargs):
        raise AssertionError("unexpected notification side effect")

    monkeypatch.setattr(
        kis_event_handler,
        "print_viewer",
        lambda *args: messages.append(args),
    )
    monkeypatch.setattr(
        kis_event_handler,
        "add_alert",
        unexpected_side_effect,
    )
    monkeypatch.setattr(
        kis_event_handler,
        "send_notification",
        unexpected_side_effect,
    )
    monkeypatch.setattr(
        kis_event_handler,
        "sync_open_orders",
        unexpected_side_effect,
    )

    row = pd.Series({"STCK_SHRN_ISCD": "005930"})

    assert kis_event_handler._handle_domestic_order(row)
    assert messages[0][0:2] == ("SYS", "ERROR")
    assert messages[0][2].startswith("Error parsing H0STCNI0:")
