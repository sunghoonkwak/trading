"""Data package.

Public data-service helpers are loaded lazily so importing ``data`` does not
initialize KIS-backed services.
"""

__all__ = ["get_portfolio_data", "invalidate_cache", "PortfolioCache"]


def __getattr__(name):
    if name in __all__:
        from . import data_service

        return getattr(data_service, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
