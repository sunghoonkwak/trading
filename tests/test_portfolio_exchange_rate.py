import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data.data_service import PortfolioProcessor
from kis.portfolio_manager import PortfolioManager
from kis.kis_api.overseas_stock.inquire_present_balance import (
    inquire_present_balance as inquire_present_balance_module,
)


class _FakeTREnv:
    my_acct = "12345678"
    my_prod = "01"


class _FailedResponse:
    def isOK(self):
        return False

    def getErrorCode(self):
        return "OPSQ1002"

    def getErrorMessage(self):
        return "SESSION FULL"

    def printError(self, url):
        return None


def test_inquire_present_balance_raises_api_error_instead_of_empty_data(monkeypatch):
    monkeypatch.setattr(
        inquire_present_balance_module.ka,
        "_url_fetch",
        lambda **kwargs: _FailedResponse(),
    )

    with pytest.raises(RuntimeError, match="OPSQ1002.*SESSION FULL"):
        inquire_present_balance_module.inquire_present_balance(
            cano="12345678",
            acnt_prdt_cd="01",
            wcrc_frcr_dvsn_cd="02",
            natn_cd="000",
            tr_mket_cd="00",
            inqr_dvsn_cd="00",
            env_dv="real",
        )


def test_fetch_portfolio_reads_exchange_rate_from_overseas_holdings(monkeypatch):
    monkeypatch.setattr(
        "kis.portfolio_manager.ka.getTREnv",
        lambda: _FakeTREnv(),
    )
    monkeypatch.setattr(
        "kis.portfolio_manager.inquire_balance",
        lambda **kwargs: (pd.DataFrame(), pd.DataFrame()),
    )
    monkeypatch.setattr(
        "kis.portfolio_manager.inquire_present_balance",
        lambda **kwargs: (
            pd.DataFrame([{"pdno": "QQQ", "bass_exrt": "1375.50"}]),
            pd.DataFrame([{"frcr_drwg_psbl_amt_1": "100.00"}]),
            pd.DataFrame(),
        ),
    )

    result = PortfolioManager._fetch_kis_account_data()

    assert result["exchange_rate"] == 1375.50


def test_kis_portfolio_uses_orderable_usd_as_cash(monkeypatch):
    calls = {}

    monkeypatch.setattr(
        "kis.portfolio_manager.ka.getTREnv",
        lambda: _FakeTREnv(),
    )
    monkeypatch.setattr(
        "kis.portfolio_manager.inquire_balance",
        lambda **kwargs: (pd.DataFrame(), pd.DataFrame()),
    )
    monkeypatch.setattr(
        "kis.portfolio_manager.inquire_present_balance",
        lambda **kwargs: (
            pd.DataFrame([{"pdno": "QQQM", "bass_exrt": "1375.50"}]),
            pd.DataFrame([{"frcr_drwg_psbl_amt_1": "999.00"}]),
            pd.DataFrame(),
        ),
    )

    def fake_inquire_psamount(**kwargs):
        calls.update(kwargs)
        return pd.DataFrame([{"ovrs_ord_psbl_amt": "3023.49"}])

    monkeypatch.setattr(
        "kis.portfolio_manager.inquire_psamount",
        fake_inquire_psamount,
        raising=False,
    )

    raw = PortfolioManager._fetch_kis_account_data()
    portfolio = PortfolioManager._convert_kis_to_standard(raw)

    usd_cash = [
        cash for cash in portfolio["cash_holdings"]
        if cash["currency"] == "USD"
    ]
    assert usd_cash[0]["amount"] == 3023.49
    assert calls["item_cd"] == "QQQM"
    assert calls["ovrs_excg_cd"] == "NASD"
    assert calls["ovrs_ord_unpr"] == "1"
    assert calls["env_dv"] == "real"


def test_kis_portfolio_falls_back_to_balance_cash_when_orderable_usd_fails(monkeypatch):
    monkeypatch.setattr(
        "kis.portfolio_manager.ka.getTREnv",
        lambda: _FakeTREnv(),
    )
    monkeypatch.setattr(
        "kis.portfolio_manager.inquire_balance",
        lambda **kwargs: (pd.DataFrame(), pd.DataFrame()),
    )
    monkeypatch.setattr(
        "kis.portfolio_manager.inquire_present_balance",
        lambda **kwargs: (
            pd.DataFrame([{"pdno": "QQQM", "bass_exrt": "1375.50"}]),
            pd.DataFrame([{"frcr_drwg_psbl_amt_1": "999.00"}]),
            pd.DataFrame(),
        ),
    )
    monkeypatch.setattr(
        "kis.portfolio_manager.inquire_psamount",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("orderable failed")),
        raising=False,
    )

    raw = PortfolioManager._fetch_kis_account_data()
    portfolio = PortfolioManager._convert_kis_to_standard(raw)

    usd_cash = [
        cash for cash in portfolio["cash_holdings"]
        if cash["currency"] == "USD"
    ]
    assert raw["error"] is None
    assert usd_cash[0]["amount"] == 999.0


def test_kis_portfolio_keeps_zero_orderable_usd(monkeypatch):
    monkeypatch.setattr(
        "kis.portfolio_manager.ka.getTREnv",
        lambda: _FakeTREnv(),
    )
    monkeypatch.setattr(
        "kis.portfolio_manager.inquire_balance",
        lambda **kwargs: (pd.DataFrame(), pd.DataFrame()),
    )
    monkeypatch.setattr(
        "kis.portfolio_manager.inquire_present_balance",
        lambda **kwargs: (
            pd.DataFrame([{"pdno": "QQQM", "bass_exrt": "1375.50"}]),
            pd.DataFrame([{"frcr_drwg_psbl_amt_1": "999.00"}]),
            pd.DataFrame(),
        ),
    )
    monkeypatch.setattr(
        "kis.portfolio_manager.inquire_psamount",
        lambda **kwargs: pd.DataFrame([{"ovrs_ord_psbl_amt": "0"}]),
        raising=False,
    )

    raw = PortfolioManager._fetch_kis_account_data()
    portfolio = PortfolioManager._convert_kis_to_standard(raw)

    usd_cash = [
        cash for cash in portfolio["cash_holdings"]
        if cash["currency"] == "USD"
    ]
    assert raw["usd_orderable"] == 0.0
    assert usd_cash == []


def test_merge_holdings_rejects_krw_assets_without_exchange_rate():
    raw_data = {
        "metadata": {"exchange_rate": 0.0},
        "asset_info": {"005930": {"currency": "KRW"}},
        "holdings": [
            {
                "ticker": "005930",
                "name": "Samsung Electronics",
                "qty": 1,
                "avg_price": 70000,
                "cur_price": 70000,
            }
        ],
        "cash_holdings": [],
    }

    with pytest.raises(ValueError, match="positive exchange rate"):
        PortfolioProcessor.merge_holdings(raw_data)
