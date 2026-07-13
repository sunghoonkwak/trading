"""Compatibility exports for the KIS portfolio infrastructure adapter."""

from infrastructure.portfolio.kis_source import (
    KisPortfolioSourceAdapter,
    fetch_kis_portfolio_source,
    get_integrated_portfolio,
)

fetch_kis_portfolio = fetch_kis_portfolio_source

__all__ = [
    "KisPortfolioSourceAdapter",
    "fetch_kis_portfolio",
    "get_integrated_portfolio",
]
