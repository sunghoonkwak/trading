import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))


def test_fetch_kis_portfolio_returns_empty_source_on_error(monkeypatch):
    from infrastructure.portfolio import kis_source
    from infrastructure.portfolio.kis_source import KisPortfolioSourceAdapter

    raw_data = {"exchange_rate": None, "error": "KIS unavailable"}
    alerts = []
    kis_source.configure_alert_publisher(
        lambda message, level: alerts.append((message, level))
    )
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

    source, metadata = kis_source.fetch_kis_portfolio_source()

    assert source == {
        "accounts": {},
        "holdings": [],
        "asset_info": {},
        "cash_holdings": [],
    }
    assert metadata is raw_data
    assert alerts == [
        ("[KIS] Fetching KIS API data...", "INFO"),
        ("KIS Error: KIS unavailable", "WARN"),
    ]
