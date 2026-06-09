# -*- coding: utf-8 -*-
"""
KIS Get Portfolio Module (Deprecated Compatibility Interface)

Compatibility wrapper for legacy callers.

New code should call PortfolioManager.get_integrated_portfolio() directly or use
an app-owned facade such as data.data_service.get_portfolio_data().
"""
from kis.portfolio_manager import PortfolioManager

def get_portfolio(kis_only: bool = False) -> dict:
    """
    Fetch and merge KIS API and GSheet data for legacy callers.

    Args:
        kis_only: If True, skip GSheet fetch and only get KIS data.

    Returns:
        dict: Standardized portfolio data.
    """
    return PortfolioManager.get_integrated_portfolio(kis_only=kis_only)
