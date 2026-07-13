import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_market_prefix_helpers_use_shared_market_mapping(monkeypatch):
    from infrastructure import trading_configuration as trading_config

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


def test_stock_configuration_is_owned_by_infrastructure():
    from infrastructure import trading_configuration as stock_configuration

    assert stock_configuration.STOCK_CONFIGURATION_PATH == (
        Path(stock_configuration.__file__).resolve().parent
        / "stock_configuration.json"
    )


def test_event_message_json_preserves_message_text():
    from interfaces.web import server as web_server

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
