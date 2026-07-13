# KIS Portfolio Source Adapter

`kis_source.py` is the infrastructure-owned KIS portfolio source adapter. It
reads KIS REST balances, normalizes holdings and orderable cash, and preserves
the existing fail-safe empty-source result when KIS reports an error.

`broker.kis_portfolio` remains a forwarding-only compatibility export for
external callers and tests while its remaining consumers migrate.
