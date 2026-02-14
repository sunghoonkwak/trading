# -*- coding: utf-8 -*-
"""
KIS Get Portfolio Module (Interface)

Main interface for the Portfolio sub-system.
Delegates all fetching and merging logic to PortfolioManager.
"""
from kis.portfolio_manager import PortfolioManager

def get_portfolio() -> dict:
    """
    Fetch and merge KIS API and GSheet data.
    
    Returns:
        dict: Standardized portfolio data.
    """
    return PortfolioManager.get_integrated_portfolio()
