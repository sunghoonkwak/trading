import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


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
