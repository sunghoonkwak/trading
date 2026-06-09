# -*- coding: utf-8 -*-
"""Application-owned facade for KIS portfolio retrieval."""


def _manager_get_integrated_portfolio(kis_only: bool = False):
    from kis.portfolio_manager import PortfolioManager

    return PortfolioManager.get_integrated_portfolio(kis_only=kis_only)


def get_integrated_portfolio(kis_only: bool = False):
    """Fetch the integrated portfolio through the existing PortfolioManager."""
    return _manager_get_integrated_portfolio(kis_only=kis_only)
