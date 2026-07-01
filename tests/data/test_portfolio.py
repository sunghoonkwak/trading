import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


@pytest.fixture(autouse=True)
def reset_gsheet_cache():
    from data import portfolio_integration

    portfolio_integration.invalidate_gsheet_cache()
    yield
    portfolio_integration.invalidate_gsheet_cache()


def test_data_integration_skips_gsheet_and_toss_for_kis_scope(monkeypatch):
    from broker import kis_portfolio, toss_portfolio
    from data import portfolio_integration

    monkeypatch.setattr(
        kis_portfolio,
        "fetch_kis_portfolio",
        lambda: (
            {
                "holdings": [],
                "cash_holdings": [],
                "asset_info": {},
                "accounts": {
                    "한국투자증권": {
                        "name": "한국투자증권",
                    }
                },
            },
            {"exchange_rate": 1375.0, "error": None},
        ),
    )
    monkeypatch.setattr(
        portfolio_integration,
        "fetch_gsheet_portfolio",
        lambda: (_ for _ in ()).throw(AssertionError("GSheet must be skipped")),
    )
    monkeypatch.setattr(
        toss_portfolio,
        "fetch_toss_portfolio",
        lambda: (_ for _ in ()).throw(AssertionError("Toss must be skipped")),
    )

    result = portfolio_integration.get_integrated_portfolio(scope="kis")

    assert "owners" not in result
    assert result["accounts"] == [
        {"id": "acc_01", "name": "한국투자증권"}
    ]
    assert result["metadata"]["exchange_rate"] == 1375.0
    assert "gsheet_error" not in result["metadata"]
    assert "toss_error" not in result["metadata"]


def test_data_integration_fetches_only_toss_for_toss_scope(monkeypatch):
    from broker import kis_portfolio, toss_portfolio
    from data import portfolio_integration

    monkeypatch.setattr(
        kis_portfolio,
        "fetch_kis_portfolio",
        lambda: (_ for _ in ()).throw(AssertionError("KIS must be skipped")),
    )
    monkeypatch.setattr(
        portfolio_integration,
        "fetch_gsheet_portfolio",
        lambda: (_ for _ in ()).throw(AssertionError("GSheet must be skipped")),
    )
    monkeypatch.setattr(
        toss_portfolio,
        "fetch_toss_portfolio",
        lambda: (
            {
                "holdings": [
                    {
                        "account_key": "토스",
                        "ticker": "AAPL",
                        "name": "Apple Inc.",
                        "qty": 2,
                        "avg_price": 150,
                        "cur_price": 160,
                    }
                ],
                "cash_holdings": [
                    {
                        "account_name": "토스",
                        "account_key": "토스",
                        "amount": 300,
                        "currency": "USD",
                    }
                ],
                "asset_info": {
                    "AAPL": {
                        "name": "Apple Inc.",
                        "market": "US",
                        "asset_type": "Stock",
                        "currency": "USD",
                    }
                },
                "accounts": {"토스": {"name": "토스"}},
            },
            None,
        ),
    )
    monkeypatch.setattr(
        portfolio_integration,
        "fetch_toss_exchange_rate",
        lambda: (1375.0, None),
    )

    result = portfolio_integration.get_integrated_portfolio(scope="toss")

    assert [account["name"] for account in result["accounts"]] == ["토스"]
    assert [holding["ticker"] for holding in result["holdings"]] == ["AAPL"]
    assert result["cash_holdings"][0]["amount"] == 300
    assert "kis_error" not in result["metadata"]
    assert "gsheet_error" not in result["metadata"]
    assert "toss_error" not in result["metadata"]


def test_data_integration_does_not_use_gsheet_fallback_for_toss_scope(monkeypatch):
    from broker import kis_portfolio, toss_portfolio
    from data import portfolio_integration

    monkeypatch.setattr(
        kis_portfolio,
        "fetch_kis_portfolio",
        lambda: (_ for _ in ()).throw(AssertionError("KIS must be skipped")),
    )
    monkeypatch.setattr(
        portfolio_integration,
        "fetch_gsheet_portfolio",
        lambda: (_ for _ in ()).throw(AssertionError("GSheet must be skipped")),
    )
    monkeypatch.setattr(
        toss_portfolio,
        "fetch_toss_portfolio",
        lambda: (_ for _ in ()).throw(RuntimeError("Toss unavailable")),
    )

    result = portfolio_integration.get_integrated_portfolio(scope="toss")

    assert result["accounts"] == []
    assert result["holdings"] == []
    assert result["cash_holdings"] == []
    assert result["metadata"]["toss_error"] == "Toss unavailable"


def test_data_integration_reuses_cached_gsheet_source(monkeypatch):
    from broker import kis_portfolio, toss_portfolio
    from data import portfolio_integration

    portfolio_integration.invalidate_gsheet_cache()
    calls = []

    monkeypatch.setattr(
        kis_portfolio,
        "fetch_kis_portfolio",
        lambda: (
            {
                "holdings": [],
                "cash_holdings": [],
                "asset_info": {},
                "accounts": {
                    "한국투자증권": {
                        "name": "한국투자증권",
                    }
                },
            },
            {"exchange_rate": 1375.0, "error": None},
        ),
    )

    def fake_fetch_gsheet():
        calls.append("fetch")
        return (
            {
                "holdings": [
                    {
                        "account_key": "ISA",
                        "ticker": "005930",
                        "name": "Samsung Electronics",
                        "qty": 1,
                        "avg_price": 70000,
                        "cur_price": 71000,
                    }
                ],
                "cash_holdings": [],
                "asset_info": {
                    "005930": {
                        "name": "Samsung Electronics",
                        "market": "KR",
                        "asset_type": "Stock",
                        "currency": "KRW",
                    }
                },
                "accounts": {"ISA": {"name": "ISA"}},
            },
            None,
        )

    monkeypatch.setattr(portfolio_integration, "fetch_gsheet_portfolio", fake_fetch_gsheet)
    monkeypatch.setattr(toss_portfolio, "fetch_toss_portfolio", lambda: ({}, "offline"))
    monkeypatch.setattr(portfolio_integration, "fetch_toss_prices", lambda tickers: {})
    monkeypatch.setattr(portfolio_integration, "send_telegram_warning", lambda message: None)

    first = portfolio_integration.get_integrated_portfolio()
    second = portfolio_integration.get_integrated_portfolio()

    assert calls == ["fetch"]
    assert [holding["ticker"] for holding in first["holdings"]] == ["005930"]
    assert [holding["ticker"] for holding in second["holdings"]] == ["005930"]


def test_refresh_gsheet_cache_replaces_cached_source(monkeypatch):
    from data import portfolio_integration

    portfolio_integration.invalidate_gsheet_cache()
    responses = [
        (
            {
                "holdings": [{"account_key": "ISA", "ticker": "OLD"}],
                "cash_holdings": [],
                "asset_info": {"OLD": {"currency": "USD"}},
                "accounts": {"ISA": {"name": "ISA"}},
            },
            None,
        ),
        (
            {
                "holdings": [{"account_key": "ISA", "ticker": "NEW"}],
                "cash_holdings": [],
                "asset_info": {"NEW": {"currency": "USD"}},
                "accounts": {"ISA": {"name": "ISA"}},
            },
            "KRW failed",
        ),
    ]

    monkeypatch.setattr(
        portfolio_integration,
        "fetch_gsheet_portfolio",
        lambda: responses.pop(0),
    )

    first_source, first_error = portfolio_integration.get_cached_gsheet_portfolio()
    refresh = portfolio_integration.refresh_gsheet_cache()
    second_source, second_error = portfolio_integration.get_cached_gsheet_portfolio()

    assert first_error is None
    assert first_source["holdings"][0]["ticker"] == "OLD"
    assert refresh["success"] is False
    assert refresh["holdings_count"] == 1
    assert refresh["error"] == "KRW failed"
    assert second_error == "KRW failed"
    assert second_source["holdings"][0]["ticker"] == "NEW"


def test_cached_gsheet_source_reports_initial_refresh_exception(monkeypatch):
    from data import portfolio_integration

    monkeypatch.setattr(
        portfolio_integration,
        "fetch_gsheet_portfolio",
        lambda: (_ for _ in ()).throw(RuntimeError("network down")),
    )

    source, error = portfolio_integration.get_cached_gsheet_portfolio()

    assert source == {
        "accounts": {},
        "holdings": [],
        "asset_info": {},
        "cash_holdings": [],
    }
    assert error == "network down"


def test_data_integration_merges_kis_and_gsheet_sources(monkeypatch):
    from broker import kis_portfolio, toss_portfolio
    from data import portfolio_integration

    monkeypatch.setattr(
        kis_portfolio,
        "fetch_kis_portfolio",
        lambda: (
            {
                "holdings": [
                    {
                        "account_key": "한국투자증권",
                        "ticker": "QQQM",
                        "name": "Invesco NASDAQ 100 ETF",
                        "qty": 2,
                        "avg_price": 100,
                        "cur_price": 110,
                    }
                ],
                "cash_holdings": [
                    {
                        "account_name": "한국투자증권",
                        "account_key": "한국투자증권",
                        "amount": 50.0,
                        "currency": "USD",
                    }
                ],
                "asset_info": {
                    "QQQM": {
                        "name": "Invesco NASDAQ 100 ETF",
                        "market": "US",
                        "asset_type": "Stock",
                        "currency": "USD",
                    }
                },
                "accounts": {
                    "한국투자증권": {
                        "name": "한국투자증권",
                    }
                },
            },
            {"exchange_rate": 1375.0, "error": None},
        ),
    )
    monkeypatch.setattr(
        portfolio_integration,
        "fetch_gsheet_portfolio",
        lambda: (
            {
                "holdings": [
                    {
                        "account_key": "ISA",
                        "ticker": "005930",
                        "name": "Samsung Electronics",
                        "qty": 1,
                        "avg_price": 70000,
                        "cur_price": 71000,
                    }
                ],
                "cash_holdings": [],
                "asset_info": {
                    "005930": {
                        "name": "Samsung Electronics",
                        "market": "KR",
                        "asset_type": "Stock",
                        "currency": "KRW",
                    }
                },
                "accounts": {
                    "ISA": {
                        "name": "ISA",
                    }
                },
            },
            None,
        ),
    )
    monkeypatch.setattr(
        toss_portfolio,
        "fetch_toss_portfolio",
        lambda: (_ for _ in ()).throw(RuntimeError("Toss unavailable")),
    )
    monkeypatch.setattr(
        portfolio_integration,
        "fetch_toss_prices",
        lambda tickers: {"005930": 72000.0},
    )

    result = portfolio_integration.get_integrated_portfolio()

    assert [account["name"] for account in result["accounts"]] == [
        "한국투자증권",
        "ISA",
    ]
    assert {holding["ticker"] for holding in result["holdings"]} == {
        "QQQM",
        "005930",
    }
    assert {
        holding["ticker"]: holding["cur_price"]
        for holding in result["holdings"]
    }["005930"] == 72000.0
    assert {cash["account_id"] for cash in result["cash_holdings"]} == {"acc_01"}
    assert result["metadata"]["toss_error"] == "Toss unavailable"


def test_data_integration_sets_missing_gsheet_prices_to_zero_and_notifies(monkeypatch):
    from broker import kis_portfolio, toss_portfolio
    from data import portfolio_integration

    notifications = []

    monkeypatch.setattr(
        kis_portfolio,
        "fetch_kis_portfolio",
        lambda: (
            {
                "holdings": [],
                "cash_holdings": [],
                "asset_info": {},
                "accounts": {},
            },
            {"exchange_rate": 1375.0, "error": None},
        ),
    )
    monkeypatch.setattr(
        portfolio_integration,
        "fetch_gsheet_portfolio",
        lambda: (
            {
                "holdings": [
                    {
                        "account_key": "ISA",
                        "ticker": "005930",
                        "name": "Samsung Electronics",
                        "qty": 1,
                        "avg_price": 70000,
                    }
                ],
                "cash_holdings": [],
                "asset_info": {
                    "005930": {
                        "name": "Samsung Electronics",
                        "market": "KR",
                        "asset_type": "Stock",
                        "currency": "KRW",
                    }
                },
                "accounts": {"ISA": {"name": "ISA"}},
            },
            None,
        ),
    )
    monkeypatch.setattr(
        toss_portfolio,
        "fetch_toss_portfolio",
        lambda: (
            {
                "holdings": [],
                "cash_holdings": [],
                "asset_info": {},
                "accounts": {"토스": {"name": "토스"}},
            },
            None,
        ),
    )
    monkeypatch.setattr(portfolio_integration, "fetch_toss_prices", lambda tickers: {})
    monkeypatch.setattr(
        portfolio_integration,
        "send_telegram_warning",
        lambda message: notifications.append(message),
    )

    result = portfolio_integration.get_integrated_portfolio()

    assert result["holdings"][0]["cur_price"] == 0.0
    assert notifications == [
        "[Portfolio] Toss current price missing for 005930; cur_price set to 0"
    ]


def test_data_integration_replaces_toss_gsheet_account_with_api(monkeypatch):
    from broker import kis_portfolio, toss_portfolio
    from data import portfolio_integration

    monkeypatch.setattr(
        kis_portfolio,
        "fetch_kis_portfolio",
        lambda: (
            {
                "holdings": [],
                "cash_holdings": [],
                "asset_info": {},
                "accounts": {},
            },
            {"exchange_rate": 1375.0, "error": None},
        ),
    )
    monkeypatch.setattr(
        portfolio_integration,
        "fetch_gsheet_portfolio",
        lambda: (
            {
                "holdings": [
                    {
                        "account_key": "토스",
                        "ticker": "OLD",
                        "name": "Old Toss Sheet Holding",
                        "qty": 9,
                        "avg_price": 1,
                        "cur_price": 1,
                    },
                    {
                        "account_key": "ISA",
                        "ticker": "005930",
                        "name": "Samsung Electronics",
                        "qty": 1,
                        "avg_price": 70000,
                        "cur_price": 71000,
                    },
                ],
                "cash_holdings": [
                    {
                        "account_name": "토스",
                        "account_key": "토스",
                        "amount": 123.0,
                        "currency": "KRW",
                    }
                ],
                "asset_info": {
                    "OLD": {
                        "name": "Old Toss Sheet Holding",
                        "market": "US",
                        "asset_type": "Stock",
                        "currency": "USD",
                    },
                    "005930": {
                        "name": "Samsung Electronics",
                        "market": "KR",
                        "asset_type": "Stock",
                        "currency": "KRW",
                    },
                },
                "accounts": {
                    "토스": {"name": "토스"},
                    "ISA": {"name": "ISA"},
                },
            },
            None,
        ),
    )
    monkeypatch.setattr(
        toss_portfolio,
        "fetch_toss_portfolio",
        lambda: (
            {
                "holdings": [
                    {
                        "account_key": "토스",
                        "ticker": "AAPL",
                        "name": "Apple Inc.",
                        "qty": 2.5,
                        "avg_price": 155.3,
                        "cur_price": 178.5,
                    }
                ],
                "cash_holdings": [
                    {
                        "account_name": "토스",
                        "account_key": "토스",
                        "amount": 3500.5,
                        "currency": "USD",
                    }
                ],
                "asset_info": {
                    "AAPL": {
                        "name": "Apple Inc.",
                        "market": "US",
                        "asset_type": "Stock",
                        "currency": "USD",
                    }
                },
                "accounts": {
                    "토스": {"name": "토스"}
                },
            },
            None,
        ),
    )
    monkeypatch.setattr(
        portfolio_integration,
        "fetch_toss_prices",
        lambda tickers: {"005930": 72000.0},
    )

    result = portfolio_integration.get_integrated_portfolio()

    assert [account["name"] for account in result["accounts"]] == ["ISA", "토스"]
    assert {holding["ticker"] for holding in result["holdings"]} == {"005930", "AAPL"}
    assert "OLD" not in result["asset_info"]
    assert result["asset_info"]["AAPL"]["currency"] == "USD"
    assert {cash["currency"]: cash["amount"] for cash in result["cash_holdings"]} == {
        "USD": 3500.5
    }
    assert "toss_error" not in result["metadata"]


def test_data_integration_keeps_gsheet_toss_when_toss_api_fails(monkeypatch):
    from broker import kis_portfolio, toss_portfolio
    from data import portfolio_integration

    monkeypatch.setattr(
        kis_portfolio,
        "fetch_kis_portfolio",
        lambda: (
            {
                "holdings": [],
                "cash_holdings": [],
                "asset_info": {},
                "accounts": {},
            },
            {"exchange_rate": 1375.0, "error": None},
        ),
    )
    monkeypatch.setattr(
        portfolio_integration,
        "fetch_gsheet_portfolio",
        lambda: (
            {
                "holdings": [
                    {
                        "account_key": "토스",
                        "ticker": "QQQM",
                        "name": "Invesco NASDAQ 100 ETF",
                        "qty": 2,
                        "avg_price": 100,
                        "cur_price": 110,
                    }
                ],
                "cash_holdings": [
                    {
                        "account_name": "토스",
                        "account_key": "토스",
                        "amount": 50.0,
                        "currency": "USD",
                    }
                ],
                "asset_info": {
                    "QQQM": {
                        "name": "Invesco NASDAQ 100 ETF",
                        "market": "US",
                        "asset_type": "Stock",
                        "currency": "USD",
                    }
                },
                "accounts": {
                    "토스": {"name": "토스"}
                },
            },
            None,
        ),
    )
    monkeypatch.setattr(
        toss_portfolio,
        "fetch_toss_portfolio",
        lambda: (_ for _ in ()).throw(RuntimeError("Toss unavailable")),
    )
    monkeypatch.setattr(
        portfolio_integration,
        "fetch_toss_prices",
        lambda tickers: {"QQQM": 123.45},
    )

    result = portfolio_integration.get_integrated_portfolio()

    assert [holding["ticker"] for holding in result["holdings"]] == ["QQQM"]
    assert result["holdings"][0]["cur_price"] == 123.45
    assert result["cash_holdings"][0]["amount"] == 50.0
    assert result["metadata"]["toss_error"] == "Toss unavailable"

