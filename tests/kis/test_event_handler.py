import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from broker import kis_event_handler


def _domestic_execution_row(quantity="1", time="091500"):
    return {
        "STCK_SHRN_ISCD": "005930",
        "STCK_CNTG_HOUR": time,
        "CNTG_YN": "2",
        "RCTF_CLS": "0",
        "RFUS_YN": "0",
        "ODER_NO": "12345678",
        "SELN_BYOV_CLS": "02",
        "CNTG_QTY": quantity,
        "CNTG_UNPR": "70000",
    }


def _capture_domestic_order_effects(monkeypatch):
    effects = {"alerts": [], "notifications": [], "removed": [], "syncs": 0}
    kis_event_handler._recent_order_events.clear()
    monkeypatch.setattr(
        kis_event_handler.trading_config,
        "get_stock_info",
        lambda _code: {"name": "Samsung"},
    )
    monkeypatch.setattr(
        kis_event_handler,
        "add_alert",
        lambda *args, **kwargs: effects["alerts"].append((args, kwargs)),
    )
    kis_event_handler.configure_notification_sender(effects["notifications"].append)
    monkeypatch.setattr(
        kis_event_handler,
        "remove_order_state",
        lambda order_no: effects["removed"].append(order_no),
    )
    monkeypatch.setattr(
        kis_event_handler,
        "sync_open_orders",
        lambda: effects.__setitem__("syncs", effects["syncs"] + 1),
    )
    return effects


def test_on_result_suppresses_duplicate_order_notifications(monkeypatch):
    effects = _capture_domestic_order_effects(monkeypatch)
    frame = pd.DataFrame([_domestic_execution_row()])

    kis_event_handler.on_result(None, "H0STCNI0", frame, {})
    kis_event_handler.on_result(None, "H0STCNI0", frame, {})

    assert len(effects["alerts"]) == 1
    assert len(effects["notifications"]) == 1
    assert effects["removed"] == ["12345678"]
    assert effects["syncs"] == 1


def test_on_result_keeps_distinct_partial_fills(monkeypatch):
    effects = _capture_domestic_order_effects(monkeypatch)

    kis_event_handler.on_result(
        None,
        "H0STCNI0",
        pd.DataFrame([_domestic_execution_row(quantity="1", time="091500")]),
        {},
    )
    kis_event_handler.on_result(
        None,
        "H0STCNI0",
        pd.DataFrame([_domestic_execution_row(quantity="2", time="091501")]),
        {},
    )

    assert len(effects["alerts"]) == 2
    assert len(effects["notifications"]) == 2
    assert effects["syncs"] == 2


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
    kis_event_handler.configure_notification_sender(unexpected_side_effect)
    monkeypatch.setattr(
        kis_event_handler,
        "sync_open_orders",
        unexpected_side_effect,
    )

    row = pd.Series({"STCK_SHRN_ISCD": "005930"})

    assert kis_event_handler._handle_domestic_order(row)
    assert messages[0][0:2] == ("SYS", "ERROR")
    assert messages[0][2].startswith("Error parsing H0STCNI0:")
