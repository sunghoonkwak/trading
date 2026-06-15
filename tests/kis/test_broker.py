import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import requests


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from broker import kis_broker
from strategy.base import OrderSide, StrategyOrder


class _FakeTREnv:
    my_acct = "12345678"
    my_prod = "01"


def test_get_orderable_usd_reads_overseas_orderable_amount(monkeypatch):
    calls = {}

    monkeypatch.setattr(
        kis_broker,
        "ka",
        SimpleNamespace(getTREnv=lambda: _FakeTREnv()),
    )
    monkeypatch.setattr(
        kis_broker.trading_config,
        "get_stock_info",
        lambda ticker: {"market": "AMS"},
    )

    def fake_inquire_psamount(**kwargs):
        calls.update(kwargs)
        return pd.DataFrame([{"ovrs_ord_psbl_amt": "3023.49"}])

    monkeypatch.setattr(kis_broker, "inquire_psamount", fake_inquire_psamount)

    amount = kis_broker.get_orderable_usd("SOXL", 25.40)

    assert amount == 3023.49
    assert calls["cano"] == "12345678"
    assert calls["acnt_prdt_cd"] == "01"
    assert calls["ovrs_excg_cd"] == "AMEX"
    assert calls["ovrs_ord_unpr"] == "25.4"
    assert calls["item_cd"] == "SOXL"
    assert calls["env_dv"] == "real"


def test_order_admin_fetches_open_orders_without_domestic_by_default(monkeypatch):
    from broker import order_admin

    calls = {}

    monkeypatch.setattr(
        order_admin,
        "_get_trenv",
        lambda: _FakeTREnv(),
    )

    def fake_inquire_psbl_rvsecncl(**kwargs):
        raise AssertionError("domestic open-order lookup must be disabled by default")

    def fake_inquire_nccs_overseas(**kwargs):
        calls["us"] = kwargs
        return pd.DataFrame([{"odno": "US1"}])

    monkeypatch.setattr(
        order_admin,
        "_get_domestic_order_endpoints",
        lambda: (_ for _ in ()).throw(
            AssertionError("domestic order endpoints must be disabled by default")
        ),
    )
    monkeypatch.setattr(
        order_admin,
        "_get_overseas_order_endpoints",
        lambda: (fake_inquire_nccs_overseas, lambda **kwargs: None),
    )

    monkeypatch.setattr(order_admin, "_fetch_toss_open_orders", lambda: pd.DataFrame())

    df, us_count, kr_count, toss_count = order_admin.fetch_open_orders()

    assert list(df["_market"]) == ["US"]
    assert (us_count, kr_count, toss_count) == (1, 0, 0)
    assert calls["us"]["cano"] == "12345678"
    assert calls["us"]["ovrs_excg_cd"] == "NASD"


def test_order_admin_fetches_domestic_open_orders_when_enabled(monkeypatch):
    from broker import order_admin

    calls = {}

    monkeypatch.setenv("KIS_ENABLE_DOMESTIC", "true")
    monkeypatch.setattr(
        order_admin,
        "_get_trenv",
        lambda: _FakeTREnv(),
    )

    def fake_inquire_psbl_rvsecncl(**kwargs):
        calls["kr"] = kwargs
        return pd.DataFrame([{"odno": "KR1"}])

    monkeypatch.setattr(
        order_admin,
        "_get_domestic_order_endpoints",
        lambda: (fake_inquire_psbl_rvsecncl, lambda **kwargs: None),
    )
    monkeypatch.setattr(
        order_admin,
        "_get_overseas_order_endpoints",
        lambda: (lambda **kwargs: pd.DataFrame(), lambda **kwargs: None),
    )
    monkeypatch.setattr(order_admin, "_fetch_toss_open_orders", lambda: pd.DataFrame())

    df, us_count, kr_count, toss_count = order_admin.fetch_open_orders()

    assert list(df["_market"]) == ["KR"]
    assert (us_count, kr_count, toss_count) == (0, 1, 0)
    assert calls["kr"]["acnt_prdt_cd"] == "01"


def test_order_admin_fetches_open_orders_from_toss(monkeypatch):
    from broker import order_admin

    monkeypatch.setattr(
        order_admin,
        "_get_trenv",
        lambda: _FakeTREnv(),
    )
    monkeypatch.setattr(
        order_admin,
        "_get_domestic_order_endpoints",
        lambda: (_ for _ in ()).throw(
            AssertionError("domestic order endpoints must be disabled by default")
        ),
    )
    monkeypatch.setattr(
        order_admin,
        "_get_overseas_order_endpoints",
        lambda: (lambda **kwargs: pd.DataFrame(), lambda **kwargs: None),
    )
    monkeypatch.setattr(
        order_admin,
        "_fetch_toss_open_orders",
        lambda: pd.DataFrame([{"orderId": "toss-1", "symbol": "AAPL"}]),
    )

    df, us_count, kr_count, toss_count = order_admin.fetch_open_orders()

    assert (us_count, kr_count, toss_count) == (0, 0, 1)
    assert df.iloc[0]["_market"] == "TOSS"
    assert df.iloc[0]["orderId"] == "toss-1"


def test_order_admin_executes_toss_cancel_through_toss_endpoint(monkeypatch):
    from broker import order_admin

    calls = {}

    monkeypatch.setattr(order_admin, "_get_toss_cancel_helpers", lambda: (
        lambda: "access-token",
        lambda access_token: 7,
        lambda **kwargs: calls.update(kwargs) or {"orderId": "toss-order-1"},
    ))

    result, message = order_admin.execute_manage_action(
        "TOSS",
        "2",
        {"odno": float("nan"), "orderId": "toss-order-1"},
    )

    assert message is None
    assert result.iloc[0]["orderId"] == "toss-order-1"
    assert calls == {
        "order_id": "toss-order-1",
        "account_seq": 7,
        "access_token": "access-token",
    }


def test_order_admin_executes_overseas_cancel_through_kis_endpoint(monkeypatch):
    from broker import order_admin

    calls = {}

    monkeypatch.setattr(
        order_admin,
        "_get_trenv",
        lambda: _FakeTREnv(),
    )
    monkeypatch.setattr(
        order_admin,
        "_get_domestic_order_endpoints",
        lambda: (_ for _ in ()).throw(
            AssertionError("domestic order endpoints are not needed for US cancel")
        ),
    )

    def fake_order_rvsecncl_overseas(**kwargs):
        calls["order"] = kwargs
        return pd.DataFrame([{"result": "ok"}]), "ok"

    monkeypatch.setattr(
        order_admin,
        "_get_overseas_order_endpoints",
        lambda: (lambda **kwargs: None, fake_order_rvsecncl_overseas),
    )

    result, message = order_admin.execute_manage_action(
        "US",
        "2",
        {"odno": "1", "pdno": "QQQM", "nccs_qty": "3"},
    )

    assert result.iloc[0]["result"] == "ok"
    assert message == "ok"
    assert calls["order"]["orgn_odno"] == "1"
    assert calls["order"]["rvse_cncl_dvsn_cd"] == "02"
    assert calls["order"]["ord_qty"] == "3"
    assert calls["order"]["env_dv"] == "real"


def test_get_orderable_usd_rejects_missing_amount(monkeypatch):
    monkeypatch.setattr(
        kis_broker,
        "ka",
        SimpleNamespace(getTREnv=lambda: _FakeTREnv()),
    )
    monkeypatch.setattr(
        kis_broker.trading_config,
        "get_stock_info",
        lambda ticker: {"market": "NASD"},
    )
    monkeypatch.setattr(
        kis_broker,
        "inquire_psamount",
        lambda **kwargs: pd.DataFrame([{"other": "0"}]),
    )

    with pytest.raises(RuntimeError, match="orderable USD"):
        kis_broker.get_orderable_usd("TQQQ", 100.0)


def test_place_overseas_order_maps_strategy_order(monkeypatch):
    calls = {}
    order = StrategyOrder(
        symbol="TQQQ",
        side=OrderSide.BUY,
        quantity=3,
        price=50.25,
        order_type="00",
    )

    monkeypatch.setattr(
        kis_broker,
        "ka",
        SimpleNamespace(getTREnv=lambda: _FakeTREnv()),
    )
    monkeypatch.setattr(
        kis_broker.trading_config,
        "get_stock_info",
        lambda ticker: {"market": "NAS"},
    )

    def fake_order_overseas_stock(**kwargs):
        calls.update(kwargs)
        return pd.DataFrame([{"odno": "1"}]), None

    monkeypatch.setattr(kis_broker, "order_overseas_stock", fake_order_overseas_stock)

    success, message = kis_broker.place_overseas_order(order)

    assert success is True
    assert message == "Success"
    assert calls["cano"] == "12345678"
    assert calls["acnt_prdt_cd"] == "01"
    assert calls["ovrs_excg_cd"] == "NASD"
    assert calls["pdno"] == "TQQQ"
    assert calls["ord_qty"] == "3"
    assert calls["ovrs_ord_unpr"] == "50.25"
    assert calls["ord_dv"] == "buy"
    assert calls["ord_dvsn"] == "00"
    assert calls["env_dv"] == "real"


def test_place_overseas_order_uses_limit_price_for_zero_price_sell(monkeypatch):
    calls = {}
    order = StrategyOrder(
        symbol="BIL",
        side=OrderSide.SELL,
        quantity=2,
        price=0,
        order_type="34",
    )

    monkeypatch.setattr(
        kis_broker,
        "ka",
        SimpleNamespace(getTREnv=lambda: _FakeTREnv()),
    )
    monkeypatch.setattr(
        kis_broker.trading_config,
        "get_stock_info",
        lambda ticker: {"market": "NASD"},
    )
    monkeypatch.setattr(
        kis_broker,
        "order_overseas_stock",
        lambda **kwargs: (calls.update(kwargs) or pd.DataFrame([{"odno": "1"}]), None),
    )

    success, _ = kis_broker.place_overseas_order(order)

    assert success is True
    assert calls["ord_dv"] == "sell"
    assert calls["ovrs_ord_unpr"] == "0.01"
    assert calls["ord_dvsn"] == "00"


def test_place_overseas_order_reports_timeout(monkeypatch):
    order = StrategyOrder(
        symbol="TQQQ",
        side=OrderSide.BUY,
        quantity=1,
        price=50.0,
    )

    monkeypatch.setattr(
        kis_broker,
        "ka",
        SimpleNamespace(getTREnv=lambda: _FakeTREnv()),
    )
    monkeypatch.setattr(
        kis_broker.trading_config,
        "get_stock_info",
        lambda ticker: {"market": "NASD"},
    )

    def raise_timeout(**kwargs):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(kis_broker, "order_overseas_stock", raise_timeout)

    success, message = kis_broker.place_overseas_order(order)

    assert success is False
    assert "[API Timeout]" in message


def test_strategy_broker_defaults_to_kis(monkeypatch):
    from broker import strategy_broker

    monkeypatch.setattr(
        strategy_broker,
        "load_json",
        lambda file_type, default=None: {},
    )

    assert strategy_broker.get_strategy_broker_name() == "kis"
    assert strategy_broker.get_strategy_account_name() == "한국투자증권"


def test_strategy_broker_selects_toss_from_strategy_config(monkeypatch):
    from broker import strategy_broker

    monkeypatch.setattr(
        strategy_broker,
        "load_json",
        lambda file_type, default=None: {"strategy_broker": "toss"},
    )

    assert strategy_broker.get_strategy_broker_name() == "toss"
    assert strategy_broker.get_strategy_account_name() == "토스"


def test_strategy_broker_rejects_unknown_broker(monkeypatch):
    from broker import strategy_broker

    monkeypatch.setattr(
        strategy_broker,
        "load_json",
        lambda file_type, default=None: {"strategy_broker": "other"},
    )

    with pytest.raises(ValueError, match="strategy_broker"):
        strategy_broker.get_strategy_broker_name()


import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

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


import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data.data_service import PortfolioProcessor
from broker.kis_portfolio import KisPortfolioSourceAdapter
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
        "broker.kis_portfolio.ka.getTREnv",
        lambda: _FakeTREnv(),
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_balance",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("domestic balance lookup must be disabled by default")
        ),
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_present_balance",
        lambda **kwargs: (
            pd.DataFrame([{"pdno": "QQQ", "bass_exrt": "1375.50"}]),
            pd.DataFrame([{"frcr_drwg_psbl_amt_1": "100.00"}]),
            pd.DataFrame(),
        ),
    )

    result = KisPortfolioSourceAdapter._fetch_kis_account_data()

    assert result["exchange_rate"] == 1375.50


def test_fetch_portfolio_skips_domestic_balance_by_default(monkeypatch):
    monkeypatch.setattr(
        "broker.kis_portfolio.ka.getTREnv",
        lambda: _FakeTREnv(),
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_balance",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("domestic balance lookup must be disabled by default")
        ),
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_present_balance",
        lambda **kwargs: (
            pd.DataFrame([{"pdno": "QQQM", "bass_exrt": "1,375.50"}]),
            pd.DataFrame([{"frcr_drwg_psbl_amt_1": "999.00"}]),
            pd.DataFrame(),
        ),
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_psamount",
        lambda **kwargs: pd.DataFrame([{"ovrs_ord_psbl_amt": "3,023.49"}]),
        raising=False,
    )

    result = KisPortfolioSourceAdapter._fetch_kis_account_data()

    assert result["domestic_stocks"] == []
    assert result["domestic_asset"] == {}
    assert result["krw_orderable"] == 0
    assert result["exchange_rate"] == 1375.50
    assert result["usd_orderable"] == 3023.49


def test_kis_portfolio_uses_orderable_usd_as_cash(monkeypatch):
    calls = {}

    monkeypatch.setattr(
        "broker.kis_portfolio.ka.getTREnv",
        lambda: _FakeTREnv(),
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_balance",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("domestic balance lookup must be disabled by default")
        ),
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_present_balance",
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
        "broker.kis_portfolio.inquire_psamount",
        fake_inquire_psamount,
        raising=False,
    )

    raw = KisPortfolioSourceAdapter._fetch_kis_account_data()
    portfolio = KisPortfolioSourceAdapter._convert_kis_to_standard(raw)

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
        "broker.kis_portfolio.ka.getTREnv",
        lambda: _FakeTREnv(),
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_balance",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("domestic balance lookup must be disabled by default")
        ),
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_present_balance",
        lambda **kwargs: (
            pd.DataFrame([{"pdno": "QQQM", "bass_exrt": "1375.50"}]),
            pd.DataFrame([{"frcr_drwg_psbl_amt_1": "999.00"}]),
            pd.DataFrame(),
        ),
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_psamount",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("orderable failed")),
        raising=False,
    )

    raw = KisPortfolioSourceAdapter._fetch_kis_account_data()
    portfolio = KisPortfolioSourceAdapter._convert_kis_to_standard(raw)

    usd_cash = [
        cash for cash in portfolio["cash_holdings"]
        if cash["currency"] == "USD"
    ]
    assert raw["error"] is None
    assert usd_cash[0]["amount"] == 999.0


def test_kis_portfolio_keeps_zero_orderable_usd(monkeypatch):
    monkeypatch.setattr(
        "broker.kis_portfolio.ka.getTREnv",
        lambda: _FakeTREnv(),
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_balance",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("domestic balance lookup must be disabled by default")
        ),
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_present_balance",
        lambda **kwargs: (
            pd.DataFrame([{"pdno": "QQQM", "bass_exrt": "1375.50"}]),
            pd.DataFrame([{"frcr_drwg_psbl_amt_1": "999.00"}]),
            pd.DataFrame(),
        ),
    )
    monkeypatch.setattr(
        "broker.kis_portfolio.inquire_psamount",
        lambda **kwargs: pd.DataFrame([{"ovrs_ord_psbl_amt": "0"}]),
        raising=False,
    )

    raw = KisPortfolioSourceAdapter._fetch_kis_account_data()
    portfolio = KisPortfolioSourceAdapter._convert_kis_to_standard(raw)

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
