# Portfolio infrastructure integration

`integration.py` implements the normalized KIS, Toss, and Google Sheets
portfolio source merge and owns the in-memory Google Sheets cache. It is an
infrastructure adapter used by `application.portfolio_service.PortfolioService`
through the `PortfolioSource` contract.

The adapter preserves partial-error metadata and notification behavior. Legacy
This module is the final implementation for portfolio source integration.
