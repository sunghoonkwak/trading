import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import requests


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
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


def test_market_data_fetch_price_delegates_to_kis_wrapper(monkeypatch):
    from broker import market_data

    calls = {}

    def fake_fetch_price(ticker, exchange=None):
        calls["args"] = (ticker, exchange)
        return 123.45

    monkeypatch.setattr(market_data, "_wrapper_fetch_price", fake_fetch_price)

    assert market_data.fetch_price("qqq", "NAS") == 123.45
    assert calls["args"] == ("qqq", "NAS")


def test_market_data_get_current_price_delegates_to_kis_wrapper(monkeypatch):
    from broker import market_data

    calls = {}

    def fake_get_current_price(ticker):
        calls["ticker"] = ticker
        return 98.76

    monkeypatch.setattr(
        market_data,
        "_wrapper_get_current_price",
        fake_get_current_price,
    )

    assert market_data.get_current_price("SOXL") == 98.76
    assert calls["ticker"] == "SOXL"


def test_order_admin_delegates_to_order_manager(monkeypatch):
    from broker import order_admin

    calls = []

    monkeypatch.setattr(
        order_admin,
        "_manager_fetch_open_orders",
        lambda: calls.append(("fetch",)) or ("df", 1, 2),
    )
    monkeypatch.setattr(
        order_admin,
        "_manager_execute_action",
        lambda market, action_type, order_data, new_price=None: (
            calls.append((market, action_type, order_data, new_price)) or ("res", None)
        ),
    )
    monkeypatch.setattr(
        order_admin,
        "_wrapper_sync_open_orders",
        lambda: calls.append(("sync",)) or True,
    )

    assert order_admin.fetch_open_orders() == ("df", 1, 2)
    assert order_admin.execute_manage_action("US", "2", {"odno": "1"}) == ("res", None)
    assert order_admin.sync_open_orders() is True
    assert calls == [
        ("fetch",),
        ("US", "2", {"odno": "1"}, None),
        ("sync",),
    ]


def test_kis_portfolio_delegates_to_portfolio_manager(monkeypatch):
    from broker import kis_portfolio

    calls = {}

    def fake_get_integrated_portfolio(kis_only=False):
        calls["kis_only"] = kis_only
        return {"accounts": []}

    monkeypatch.setattr(
        kis_portfolio,
        "_manager_get_integrated_portfolio",
        fake_get_integrated_portfolio,
    )

    assert kis_portfolio.get_integrated_portfolio(kis_only=True) == {"accounts": []}
    assert calls["kis_only"] is True


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
