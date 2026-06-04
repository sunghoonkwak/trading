import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_portfolio_keyboard_uses_tltw_instead_of_tqqq():
    stock_config = json.loads((ROOT / "src/stock_configuration.json").read_text(encoding="utf-8"))
    button_tickers = [
        stock["ticker"]
        for region in ["KR", "US"]
        for stock in stock_config.get(region, [])
        if stock.get("telegram_button", False)
    ]

    assert "TLTW" in button_tickers
    assert "TQQQ" not in button_tickers


def test_event_viewer_fixed_order_ends_with_vixy():
    app_js = ROOT / "src/web/static/app.js"
    source = app_js.read_text(encoding="utf-8")

    ticker_order = re.search(r"const tickerOrder = \[(.*?)\];", source, re.S).group(1)
    tickers = re.findall(r"'([A-Z]+)'", ticker_order)

    assert tickers[-1] == "VIXY"
    assert "'VIXY': 'PROSHARES VIX SHORT TERM FUTURES'" in source
