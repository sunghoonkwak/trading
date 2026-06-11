import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_update_order_state_sends_broker_after_quantity(monkeypatch):
    from core import display

    sent = []

    class FakePipe:
        def send_log(self, *args):
            sent.append(args)

    monkeypatch.setattr(display, "_get_event_pipe", lambda: FakePipe())

    display.update_order_state(
        "order-1",
        "AAPL",
        "Apple Inc.",
        "Buy",
        "185.50",
        "3",
        "PLACED",
        notify=False,
        broker="TOSS",
        time_str="10:11:12",
    )

    assert sent == [
        (
            "ODR",
            "Apple Inc.          |AAPL|Buy|3|TOSS|185.50|PLACED|order-1",
            "10:11:12",
        )
    ]
