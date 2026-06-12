import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from broker import market_data
from broker.kis_portfolio import KisPortfolioSourceAdapter
from kis.kis_api.overseas_stock.price import price as price_module
from kis.kis_api import kis_auth as ka


class _FakeTREnv:
    my_acct = "12345678"
    my_prod = "01"


def test_portfolio_fetch_uses_real_env_even_when_paper_flag_is_true(monkeypatch):
    calls = {}

    monkeypatch.setattr(ka, "getTREnv", lambda: _FakeTREnv())
    monkeypatch.setattr(ka, "isPaperTrading", lambda: True)

    def fake_inquire_balance(**kwargs):
        raise AssertionError("domestic balance lookup must be disabled by default")

    def fake_inquire_present_balance(**kwargs):
        calls["overseas_env"] = kwargs["env_dv"]
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_balance",
        fake_inquire_balance,
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_present_balance",
        fake_inquire_present_balance,
    )

    KisPortfolioSourceAdapter._fetch_kis_account_data()

    assert calls == {
        "overseas_env": "real",
    }


def test_price_fetch_uses_real_env_even_when_paper_flag_is_true(monkeypatch):
    calls = {}

    monkeypatch.setattr(ka, "isPaperTrading", lambda: True)
    monkeypatch.setattr(
        market_data.trading_config,
        "get_kis_exchange_code",
        lambda ticker: "NAS",
    )

    def fake_price(auth, exchange, ticker, env_dv):
        calls["price_args"] = (auth, exchange, ticker, env_dv)
        return pd.DataFrame([{"last": "123.45"}])

    monkeypatch.setattr(price_module, "price", fake_price)

    result = market_data.fetch_price("qqq")

    assert result == 123.45
    assert calls["price_args"] == ("", "NAS", "QQQ", "real")
