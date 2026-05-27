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
