import sys
import types
from pathlib import Path
import importlib.util

import pandas as pd

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from state import market_state


def _load_event_handler(monkeypatch):
    fake_kis = types.ModuleType("kis")
    fake_event_pipe = types.ModuleType("kis.event_pipe")
    fake_event_pipe.print_viewer = lambda *args, **kwargs: None
    fake_ws_parser = types.ModuleType("kis.ws_parser")
    fake_ws_parser.mask_dict_for_log = lambda value: value
    fake_kis.event_pipe = fake_event_pipe
    fake_kis.ws_parser = fake_ws_parser
    fake_broker = types.ModuleType("broker")
    fake_order_admin = types.ModuleType("broker.order_admin")
    fake_order_admin.sync_open_orders = lambda: None
    fake_telegram_bot = types.ModuleType("telegram_bot")
    fake_telegram_utils = types.ModuleType("telegram_bot.telegram_utils")
    fake_telegram_utils.send_notification = lambda *args, **kwargs: None

    monkeypatch.setitem(sys.modules, "kis", fake_kis)
    monkeypatch.setitem(sys.modules, "kis.event_pipe", fake_event_pipe)
    monkeypatch.setitem(sys.modules, "kis.ws_parser", fake_ws_parser)
    monkeypatch.setitem(sys.modules, "broker", fake_broker)
    monkeypatch.setitem(sys.modules, "broker.order_admin", fake_order_admin)
    monkeypatch.setitem(sys.modules, "telegram_bot", fake_telegram_bot)
    monkeypatch.setitem(sys.modules, "telegram_bot.telegram_utils", fake_telegram_utils)

    spec = importlib.util.spec_from_file_location(
        "event_handler_under_test",
        SRC_DIR / "kis" / "event_handler.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_domestic_tick_updates_market_state_manager(monkeypatch):
    event_handler = _load_event_handler(monkeypatch)
    manager = market_state.get_market_manager()
    manager._data.clear()
    manager._first_data_received = False
    manager._persistence_running = False

    started = {}

    def fake_start_periodic_save():
        started["called"] = True

    monkeypatch.setattr(manager, "_start_periodic_save", fake_start_periodic_save)
    monkeypatch.setattr(event_handler.trading_config, "get_stock_info", lambda code: None)

    row = pd.Series(
        {
            "MKSC_SHRN_ISCD": "005930",
            "STCK_CNTG_HOUR": "091500",
            "STCK_PRPR": "70000",
            "CNTG_VOL": "12",
            "PRDY_VRSS": "100",
            "PRDY_CTRT": "0.14",
            "PRDY_VRSS_SIGN": "2",
        }
    )

    assert event_handler._handle_domestic_market("H0UNCNT0", row) is True

    ticker = manager.get_ticker("005930")
    assert ticker["price"] == 70000
    assert ticker["change"] == 100
    assert ticker["rate"] == 0.14
    assert ticker["vol"] == 12
    assert ticker["time"] == "091500"
    assert started == {"called": True}
