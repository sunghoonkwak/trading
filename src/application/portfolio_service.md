# Portfolio retrieval use case

`portfolio_service.py` assembles the normalized portfolio result from injected
infrastructure collaborators. It does not cache the final result: every call
uses the portfolio source, while the infrastructure integration alone owns the
slow Google Sheets source cache.

`scope="all"`, `"kis"`, and `"toss"` preserve the established account and
cash filtering rules. `all` may retain safe partial source data; broker-only
scopes are used for strategy decisions and only expose their selected account.
Invalid or missing exchange rates must not create an incorrect aggregate.

The service returns raw source data, merged holdings, total USD value, stats,
price map, account/holding lists, metadata, current weights, and targets.
