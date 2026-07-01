import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_market_prefix_helpers_use_shared_market_mapping(monkeypatch):
    from core import trading_config

    monkeypatch.setattr(
        trading_config,
        "CONFIG",
        {
            "KR": [{"ticker": "005930", "name": "Samsung", "market": "KOSPI"}],
            "US": [{"ticker": "IBM", "name": "IBM", "market": "NYSE"}],
        },
    )

    assert trading_config.strip_market_prefix("DNYSIBM") == "IBM"
    assert trading_config.get_stock_info("DNYSIBM")["ticker"] == "IBM"
    assert trading_config.get_kis_exchange_code("IBM") == "NYS"
    assert trading_config.get_kis_market_prefix("IBM") == "DNYSIBM"
    assert trading_config.get_kis_market_prefix("DNYSIBM") == "DNYSIBM"


def test_event_message_json_preserves_message_text():
    from core import web_server

    payload = json.loads(
        web_server._event_message_json(
            "ALT",
            'price "SOXL" \\ check',
            "09:30:00",
        )
    )

    assert payload == {
        "type": "ALT",
        "data": 'price "SOXL" \\ check',
        "time": "09:30:00",
    }
