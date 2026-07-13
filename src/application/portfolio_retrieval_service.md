# Portfolio Retrieval Service

`PortfolioRetrievalService` owns the application policy for choosing KIS,
Toss, and cached Google Sheets sources, merging their normalized data, and
retaining partial-error metadata. It receives every external read, cache, price
lookup, and alert action as an injected callable.

`main.py` composes the service with infrastructure adapters. The service does
not import KIS, Toss, Google Sheets, configuration, or notification modules.
Google Sheets remains the owner of its in-memory cache; this service only
decides when cached data is used.
