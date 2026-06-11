import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telegram_bot.telegram_portfolio import build_ticker_keyboard, format_placed_orders


def test_ticker_keyboard_fallback_uses_top_portfolio_targets(monkeypatch):
    def raise_config_error(*args, **kwargs):
        raise OSError("missing config")

    monkeypatch.setattr("builtins.open", raise_config_error)

    keyboard = build_ticker_keyboard({
        "merged_data": {
            "CASH_USD": {"type": "CASH"},
            "SOXL": {"type": "STOCK"},
            "TLTW": {"type": "STOCK"},
            "SCHD": {"type": "STOCK"},
        },
        "targets": {
            "SCHD": 0.05,
            "SOXL": 0.20,
            "TLTW": 0.10,
        },
    })

    buttons = [
        button.text
        for row in keyboard.inline_keyboard
        for button in row
    ]

    assert buttons == ["SOXL", "TLTW", "SCHD"]


def test_format_placed_orders_groups_by_ticker():
    df = pd.DataFrame([
        {
            "_market": "US",
            "pdno": "SOXL",
            "prdt_name": "DIREXION SEMICONDUCTOR DAILY 3X",
            "sll_buy_dvsn_cd": "01",
            "sll_buy_dvsn_cd_name": "LOC매도",
            "ft_ord_unpr3": "250.12",
            "nccs_qty": "7",
        },
        {
            "_market": "US",
            "pdno": "SOXL",
            "prdt_name": "DIREXION SEMICONDUCTOR DAILY 3X",
            "sll_buy_dvsn_cd": "01",
            "sll_buy_dvsn_cd_name": "매도",
            "ft_ord_unpr3": "250.12",
            "nccs_qty": "8",
        },
        {
            "_market": "US",
            "pdno": "SOXL",
            "prdt_name": "DIREXION SEMICONDUCTOR DAILY 3X",
            "sll_buy_dvsn_cd": "02",
            "sll_buy_dvsn_cd_name": "LOC매수",
            "ft_ord_unpr3": "243.91",
            "nccs_qty": "4",
        },
        {
            "_market": "US",
            "pdno": "FAS",
            "prdt_name": "DIREXION FINANCIAL DAILY 3X",
            "sll_buy_dvsn_cd": "02",
            "sll_buy_dvsn_cd_name": "LOC매수",
            "ft_ord_unpr3": "140.48",
            "nccs_qty": "1",
        },
    ])

    msg = format_placed_orders(df, num_us=4, num_kr=0)

    assert msg == "\n".join([
        "📋 <b>Open Orders</b> (US: 4 / KR: 0)",
        "",
        "<b>SOXL</b>",
        "🔴 <b>Sell</b>",
        "  LOC매도  7 @ $250.12",
        "  매도     8 @ $250.12",
        "🟢 <b>Buy</b>",
        "  LOC매수  4 @ $243.91",
        "",
        "<b>FAS</b>",
        "🟢 <b>Buy</b>",
        "  LOC매수  1 @ $140.48",
    ])


def test_format_placed_orders_includes_toss_orders():
    df = pd.DataFrame([
        {
            "_market": "TOSS",
            "symbol": "AAPL",
            "side": "BUY",
            "orderType": "LIMIT",
            "price": "185.5",
            "remainingQuantity": "3",
        },
        {
            "_market": "TOSS",
            "symbol": "005930",
            "side": "SELL",
            "orderType": "MARKET",
            "quantity": "2",
        },
    ])

    msg = format_placed_orders(df, num_us=0, num_kr=0, num_toss=2)

    assert msg == "\n".join([
        "📋 <b>Open Orders</b> (US: 0 / KR: 0 / Toss: 2)",
        "",
        "<b>AAPL</b>",
        "🟢 <b>Buy</b>",
        "  LIMIT  3 @ $185.50",
        "",
        "<b>005930</b>",
        "🔴 <b>Sell</b>",
        "  MARKET  2 @ Market",
    ])
