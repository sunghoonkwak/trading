# -*- coding: utf-8 -*-
"""Application-owned facade for KIS portfolio retrieval."""


def _empty_source():
    return {
        "accounts": {},
        "holdings": [],
        "asset_info": {},
        "cash_holdings": [],
    }


def fetch_kis_portfolio():
    """Fetch KIS holdings and convert them to the standard source format."""
    from core.display import add_alert
    from kis.portfolio_manager import KisPortfolioSourceAdapter

    add_alert("[KIS] Fetching KIS API data...", "INFO")
    kis_raw_data = KisPortfolioSourceAdapter._fetch_kis_account_data()

    if kis_raw_data.get("error"):
        add_alert(f"KIS Error: {kis_raw_data['error']}", "WARN")
        return _empty_source(), kis_raw_data

    kis_portfolio = KisPortfolioSourceAdapter._convert_kis_to_standard(kis_raw_data)
    add_alert(
        f"[KIS] {len(kis_portfolio.get('holdings', []))} holdings loaded",
        "SUCCESS",
    )
    return kis_portfolio, kis_raw_data


def _manager_get_integrated_portfolio(kis_only: bool = False):
    from data.portfolio_integration import get_integrated_portfolio

    return get_integrated_portfolio(kis_only=kis_only)


def get_integrated_portfolio(kis_only: bool = False):
    """Fetch the integrated portfolio through the data integration layer."""
    return _manager_get_integrated_portfolio(kis_only=kis_only)
