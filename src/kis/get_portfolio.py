# -*- coding: utf-8 -*-
"""
KIS Get Portfolio Module (Interface)

Main interface for the Portfolio sub-system.
Delegates all fetching and merging logic to PortfolioManager.
"""
from kis.portfolio_manager import PortfolioManager

def get_portfolio(kis_only: bool = False) -> dict:
    """
    Fetch and merge KIS API and GSheet data.

    Args:
        kis_only: If True, skip GSheet fetch and only get KIS data.

    Returns:
        dict: Standardized portfolio data.
    """
    return PortfolioManager.get_integrated_portfolio(kis_only=kis_only)
