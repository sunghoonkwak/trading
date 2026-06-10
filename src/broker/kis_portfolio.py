# -*- coding: utf-8 -*-
"""Application-owned facade for portfolio retrieval through the KIS worker."""


def _manager_get_integrated_portfolio(kis_only: bool = False):
    from data.portfolio_integration import get_integrated_portfolio

    return get_integrated_portfolio(kis_only=kis_only)


def get_integrated_portfolio(kis_only: bool = False):
    """Fetch the integrated portfolio through the existing PortfolioManager."""
    return _manager_get_integrated_portfolio(kis_only=kis_only)
