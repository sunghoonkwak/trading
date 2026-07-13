# Portfolio Weight Rules (`src/domain/portfolio/weights.py`)

Pure allocation rules calculate target weights and rebalancing differences from
in-memory portfolio configuration and current weights.

- Fear & Greed selects `cash_strategy.min`, `.mid`, or `.max`.
- Extreme Fear adds the fixed SOXL and TQQQ leverage sleeves.
- Core scores and satellite ratios determine the remaining stock allocation.
- `Bonds` groups are cash-like and receive no target allocation; group
constituents are merged into their main ticker for current weights.
- `weighted_split` strategies distribute their target by constituent weight.

File configuration and external market data are outside this domain module.
