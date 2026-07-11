"""Deprecated compatibility exports for portfolio scheduler interfaces."""

from data.data_service import get_portfolio_data
from interfaces.scheduler.portfolio_runner import REPORTS_DIR
from interfaces.scheduler.portfolio_runner import run_daily_portfolio_report as _run_report

__all__ = ["REPORTS_DIR", "run_daily_portfolio_report"]


class _PortfolioReader:
    def get_portfolio_data(self):
        return get_portfolio_data()


def run_daily_portfolio_report():
    """Run the portfolio scheduler with the legacy data-service adapter."""
    return _run_report(_PortfolioReader())
