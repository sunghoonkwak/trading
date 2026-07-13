# Portfolio infrastructure integration

`integration.py` implements the normalized KIS, Toss, and Google Sheets
portfolio source merge and owns the in-memory Google Sheets cache. It is an
infrastructure adapter used by `application.portfolio_service.PortfolioService`
through the `PortfolioSource` contract.

The adapter preserves partial-error metadata and notification behavior. Local
alert publication and optional Telegram warnings are injected from `main.py`,
so this adapter does not import the legacy display or interface packages.
Legacy
This module is the final implementation for portfolio source integration.
