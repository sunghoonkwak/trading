import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telegram_bot.telegram_portfolio import build_ticker_keyboard


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
