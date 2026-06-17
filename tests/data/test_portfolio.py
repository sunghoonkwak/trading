import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_data_integration_skips_gsheet_and_toss_for_kis_scope(monkeypatch):
    from broker import portfolio
    from data import portfolio_integration

    monkeypatch.setattr(
        portfolio,
        "fetch_kis_source",
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
        portfolio,
        "fetch_toss_source",
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
    from broker import portfolio
    from data import portfolio_integration

    monkeypatch.setattr(
        portfolio,
        "fetch_kis_source",
        lambda: (_ for _ in ()).throw(AssertionError("KIS must be skipped")),
    )
    monkeypatch.setattr(
        portfolio_integration,
        "fetch_gsheet_portfolio",
        lambda: (_ for _ in ()).throw(AssertionError("GSheet must be skipped")),
    )
    monkeypatch.setattr(
        portfolio,
        "fetch_toss_source",
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
    from broker import portfolio
    from data import portfolio_integration

    monkeypatch.setattr(
        portfolio,
        "fetch_kis_source",
        lambda: (_ for _ in ()).throw(AssertionError("KIS must be skipped")),
    )
    monkeypatch.setattr(
        portfolio_integration,
        "fetch_gsheet_portfolio",
        lambda: (_ for _ in ()).throw(AssertionError("GSheet must be skipped")),
    )
    monkeypatch.setattr(
        portfolio,
        "fetch_toss_source",
        lambda: (_ for _ in ()).throw(RuntimeError("Toss unavailable")),
    )

    result = portfolio_integration.get_integrated_portfolio(scope="toss")

    assert result["accounts"] == []
    assert result["holdings"] == []
    assert result["cash_holdings"] == []
    assert result["metadata"]["toss_error"] == "Toss unavailable"


def test_data_integration_merges_kis_and_gsheet_sources(monkeypatch):
    from broker import portfolio
    from data import portfolio_integration

    monkeypatch.setattr(
        portfolio,
        "fetch_kis_source",
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
        portfolio,
        "fetch_toss_source",
        lambda: (_ for _ in ()).throw(RuntimeError("Toss unavailable")),
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
    assert result["metadata"]["toss_error"] == "Toss unavailable"


def test_data_integration_replaces_toss_gsheet_account_with_api(monkeypatch):
    from broker import portfolio
    from data import portfolio_integration

    monkeypatch.setattr(
        portfolio,
        "fetch_kis_source",
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
        portfolio,
        "fetch_toss_source",
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
    from broker import portfolio
    from data import portfolio_integration

    monkeypatch.setattr(
        portfolio,
        "fetch_kis_source",
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
        portfolio,
        "fetch_toss_source",
        lambda: (_ for _ in ()).throw(RuntimeError("Toss unavailable")),
    )

    result = portfolio_integration.get_integrated_portfolio()

    assert [holding["ticker"] for holding in result["holdings"]] == ["QQQM"]
    assert result["cash_holdings"][0]["amount"] == 50.0
    assert result["metadata"]["toss_error"] == "Toss unavailable"


def test_fetch_kis_portfolio_returns_empty_source_on_error(monkeypatch):
    from broker import kis_portfolio
    from broker.kis_portfolio import KisPortfolioSourceAdapter

    raw_data = {"exchange_rate": None, "error": "KIS unavailable"}
    monkeypatch.setattr(
        KisPortfolioSourceAdapter,
        "_fetch_kis_account_data",
        staticmethod(lambda: raw_data),
    )
    monkeypatch.setattr(
        KisPortfolioSourceAdapter,
        "_convert_kis_to_standard",
        staticmethod(
            lambda fetched: (_ for _ in ()).throw(
                AssertionError("conversion must be skipped")
            )
        ),
    )

    source, metadata = kis_portfolio.fetch_kis_portfolio()

    assert source == {
        "accounts": {},
        "holdings": [],
        "asset_info": {},
        "cash_holdings": [],
    }
    assert metadata is raw_data


def test_fetch_toss_portfolio_converts_api_payload(monkeypatch):
    from broker import toss_portfolio

    captured = {"buying_power": []}

    monkeypatch.setattr(
        "toss.auth.load_access_token",
        lambda: "access-token",
    )
    monkeypatch.setattr(
        "toss.get_holdings.get_holdings",
        lambda **kwargs: {
            "items": [
                {
                    "symbol": "005930",
                    "name": "삼성전자",
                    "marketCountry": "KR",
                    "currency": "KRW",
                    "quantity": "10",
                    "lastPrice": "72000",
                    "averagePurchasePrice": "65000",
                },
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "marketCountry": "US",
                    "currency": "USD",
                    "quantity": "2.5",
                    "lastPrice": "178.5",
                    "averagePurchasePrice": "155.3",
                },
            ]
        },
    )

    def fake_buying_power(**kwargs):
        captured["buying_power"].append(kwargs)
        return {
            "currency": kwargs["currency"],
            "cashBuyingPower": "5000000" if kwargs["currency"] == "KRW" else "3500.5",
        }

    monkeypatch.setattr("toss.get_buying_power.get_buying_power", fake_buying_power)

    source, error = toss_portfolio.fetch_toss_portfolio()

    assert error is None
    assert source["accounts"] == {
        "토스": {"name": "토스"}
    }
    assert source["holdings"] == [
        {
            "account_key": "토스",
            "ticker": "005930",
            "name": "삼성전자",
            "qty": 10.0,
            "avg_price": 65000.0,
            "cur_price": 72000.0,
        },
        {
            "account_key": "토스",
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "qty": 2.5,
            "avg_price": 155.3,
            "cur_price": 178.5,
        },
    ]
    assert source["asset_info"]["005930"]["market"] == "KR"
    assert source["asset_info"]["AAPL"]["currency"] == "USD"
    assert source["cash_holdings"] == [
        {
            "account_name": "토스",
            "account_key": "토스",
            "amount": 5000000.0,
            "currency": "KRW",
        },
        {
            "account_name": "토스",
            "account_key": "토스",
            "amount": 3500.5,
            "currency": "USD",
        },
    ]
    assert [call["currency"] for call in captured["buying_power"]] == ["KRW", "USD"]


def test_data_service_toss_scope_filters_toss_account(monkeypatch):
    from data import data_service

    raw = {
        "metadata": {"exchange_rate": 1300.0},
        "asset_info": {
            "QQQM": {"currency": "USD"},
            "AAPL": {"currency": "USD"},
        },
        "accounts": [
            {"id": "acc_01", "name": "한국투자증권"},
            {"id": "acc_02", "name": "토스"},
        ],
        "holdings": [
            {
                "account_id": "acc_01",
                "ticker": "QQQM",
                "name": "QQQM",
                "qty": 1,
                "avg_price": 100,
                "cur_price": 100,
            },
            {
                "account_id": "acc_02",
                "ticker": "AAPL",
                "name": "Apple",
                "qty": 2,
                "avg_price": 150,
                "cur_price": 160,
            },
        ],
        "cash_holdings": [
            {
                "account_id": "acc_01",
                "account_name": "한국투자증권",
                "amount": 10,
                "currency": "USD",
            },
            {
                "account_id": "acc_02",
                "account_name": "토스",
                "amount": 20,
                "currency": "USD",
            },
        ],
    }
    data = {
        "raw": raw,
        "merged_data": {},
        "total_value_usd": 0,
        "stats": {},
        "accounts": raw["accounts"],
        "holdings": raw["holdings"],
        "metadata": raw["metadata"],
    }

    scoped = data_service._apply_scope_filter(data, "toss")

    assert {holding["ticker"] for holding in scoped["holdings"]} == {"AAPL"}
    assert set(scoped["merged_data"]) == {"AAPL", "USD cash"}
    assert scoped["merged_data"]["USD cash"]["qty"] == 20


def test_data_service_passes_scope_to_portfolio_worker(monkeypatch):
    from data import data_service

    captured = {}

    class Response:
        success = False
        error = "stop after request"

    monkeypatch.setattr(data_service.PortfolioCacheManager, "get", lambda force: None)
    monkeypatch.setattr(data_service, "is_kis_ready", lambda: True)
    monkeypatch.setattr(data_service, "add_alert", lambda message, level: None)
    monkeypatch.setattr(
        data_service,
        "request_portfolio",
        lambda force_refresh=False, scope="all": captured.update(
            {"force_refresh": force_refresh, "scope": scope}
        ) or "request-1",
    )
    monkeypatch.setattr(
        data_service,
        "wait_for_response",
        lambda request_id, timeout=60.0: Response(),
    )

    result = data_service.get_portfolio_data(force_refresh=True, scope="toss")

    assert result == {"error": "stop after request"}
    assert captured == {"force_refresh": True, "scope": "toss"}


import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC_DIR))

from data.gsheet import parse_worksheet_data


class FakeWorksheet:
    def __init__(self, rows):
        self.rows = rows

    def get_all_values(self):
        return self.rows


def test_cash_only_gsheet_accounts_get_account_ids():
    worksheet = FakeWorksheet([
        ["ticker", "name", "qty", "avg_price", "investment", "account", "cur_price"],
        ["", "", "", "", "", "", ""],
        ["예수금", "예수금", "48824198", "", "", "CMA", ""],
        ["예수금", "예수금", "1028394", "", "", "CMA 보조", ""],
    ])

    parsed = parse_worksheet_data(worksheet, "KRW")

    assert parsed["accounts"] == {
        "CMA": {"name": "CMA"},
        "CMA 보조": {"name": "CMA 보조"},
    }
    assert parsed["cash_holdings"] == [
        {
            "account_name": "CMA",
            "account_key": "CMA",
            "amount": 48824198.0,
            "currency": "KRW",
        },
        {
            "account_name": "CMA 보조",
            "account_key": "CMA 보조",
            "amount": 1028394.0,
            "currency": "KRW",
        },
    ]
