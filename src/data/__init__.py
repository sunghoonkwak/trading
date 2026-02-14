# Data module - centralized data access layer
from .data_service import (
    get_portfolio_data,
    invalidate_cache,
    PortfolioCache
)
