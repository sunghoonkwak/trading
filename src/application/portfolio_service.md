# Portfolio retrieval use case

`portfolio_service.py` assembles the normalized portfolio result from injected
infrastructure collaborators. It does not cache the final result: every call
uses the portfolio source, while the infrastructure integration alone owns the
slow Google Sheets source cache.

`scope="all"`, `"kis"`, and `"toss"` preserve the established account and
cash filtering rules. `all` may retain safe partial source data; broker-only
scopes recalculate holdings, cash, totals, statistics, and current weights for
the selected broker. The returned `accounts` list remains the raw source list.
Invalid or missing exchange rates must not create an incorrect aggregate.

The service returns raw source data, merged holdings, total USD value, stats,
price map, account/holding lists, metadata, current weights, and targets.
