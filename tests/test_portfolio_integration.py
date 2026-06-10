import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_data_integration_skips_gsheet_for_kis_only(monkeypatch):
    from data import portfolio_integration

    monkeypatch.setattr(
        portfolio_integration,
        "_fetch_kis_portfolio",
        lambda: (
            {
                "holdings": [],
                "cash_holdings": [],
                "asset_info": {},
                "accounts": {
                    "한국투자증권_owner_01": {
                        "name": "한국투자증권",
                        "owner_id": "owner_01",
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

    result = portfolio_integration.get_integrated_portfolio(kis_only=True)

    assert result["accounts"] == [
        {"id": "acc_01", "owner_id": "owner_01", "name": "한국투자증권"}
    ]
    assert result["metadata"]["exchange_rate"] == 1375.0
    assert "gsheet_error" not in result["metadata"]


def test_data_integration_merges_kis_and_gsheet_sources(monkeypatch):
    from data import portfolio_integration

    monkeypatch.setattr(
        portfolio_integration,
        "_fetch_kis_portfolio",
        lambda: (
            {
                "holdings": [
                    {
                        "account_key": "한국투자증권_owner_01",
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
                        "account_key": "한국투자증권_owner_01",
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
                    "한국투자증권_owner_01": {
                        "name": "한국투자증권",
                        "owner_id": "owner_01",
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
                        "account_key": "ISA_owner_01",
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
                    "ISA_owner_01": {
                        "name": "ISA",
                        "owner_id": "owner_01",
                    }
                },
            },
            None,
        ),
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
    assert {cash["account_id"] for cash in result["cash_holdings"]} == {"acc_01"}
