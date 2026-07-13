# Market Signals Adapter (`src/infrastructure/market_signals.py`)

The adapter owns external US market-calendar and Fear & Greed calls, including
the established fail-open calendar behavior and ten-minute sentiment cache.
`main.py` injects its functions into application and interface collaborators.
